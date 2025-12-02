"""
Utilization Service

Calculates utilization metrics using a Gaussian-weighted composite score.
"""
from datetime import timedelta
import math
import os
from typing import Optional

from .normalization import Normalization
from .internal_transactions import InternalTransaction


class PaycheckInfo:
    def __init__(self, avg_paycheck_cents: int, period_days: int, paycheck_confidence: float):
        self.avg_paycheck_cents = avg_paycheck_cents
        self.period_days = period_days
        self.paycheck_confidence = paycheck_confidence


class UtilizationConfig:
    """Configuration class for Gaussian scoring parameters."""
    
    DEFAULT_UTILIZATION_PARAMS = (0.6, 0.3, 0.45)
    DEFAULT_BURN_DAYS_PARAMS = (30.0, 15.0, 0.35)
    DEFAULT_DAILY_SPEND_PARAMS = (0.033, 0.02, 0.20)
    DEFAULT_LABEL_THRESHOLDS = [
        (80, "healthy"),
        (60, "medium-risk"),
        (40, "high-risk"),
        (20, "very-high-risk"),
        (0, "critical-risk"),
    ]
    
    def __init__(
        self,
        utilization_params: Optional[tuple[float, float, float]] = None,
        burn_days_params: Optional[tuple[float, float, float]] = None,
        daily_spend_params: Optional[tuple[float, float, float]] = None,
        label_thresholds: Optional[list[tuple[int, str]]] = None,
        load_from_env: bool = True
    ):
        if utilization_params:
            self.utilization_params = utilization_params
        elif load_from_env and os.getenv("UTIL_MU"):
            self.utilization_params = (
                float(os.getenv("UTIL_MU", "0.6")),
                float(os.getenv("UTIL_SIGMA", "0.3")),
                float(os.getenv("UTIL_WEIGHT", "0.45"))
            )
        else:
            self.utilization_params = self.DEFAULT_UTILIZATION_PARAMS
        
        if burn_days_params:
            self.burn_days_params = burn_days_params
        elif load_from_env and os.getenv("BURN_MU"):
            self.burn_days_params = (
                float(os.getenv("BURN_MU", "30.0")),
                float(os.getenv("BURN_SIGMA", "15.0")),
                float(os.getenv("BURN_WEIGHT", "0.35"))
            )
        else:
            self.burn_days_params = self.DEFAULT_BURN_DAYS_PARAMS
        
        if daily_spend_params:
            self.daily_spend_params = daily_spend_params
        elif load_from_env and os.getenv("SPEND_MU"):
            self.daily_spend_params = (
                float(os.getenv("SPEND_MU", "0.033")),
                float(os.getenv("SPEND_SIGMA", "0.02")),
                float(os.getenv("SPEND_WEIGHT", "0.20"))
            )
        else:
            self.daily_spend_params = self.DEFAULT_DAILY_SPEND_PARAMS
        
        if label_thresholds:
            self.label_thresholds = label_thresholds
        elif load_from_env and os.getenv("LABEL_HEALTHY"):
            self.label_thresholds = [
                (int(os.getenv("LABEL_HEALTHY", "80")), "healthy"),
                (int(os.getenv("LABEL_MEDIUM", "60")), "medium-risk"),
                (int(os.getenv("LABEL_HIGH", "40")), "high-risk"),
                (int(os.getenv("LABEL_VERY_HIGH", "20")), "very-high-risk"),
                (0, "critical-risk"),
            ]
        else:
            self.label_thresholds = self.DEFAULT_LABEL_THRESHOLDS
        
        total_weight = (
            self.utilization_params[2] + 
            self.burn_days_params[2] + 
            self.daily_spend_params[2]
        )
        if abs(total_weight - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {total_weight}")


class UtilizationService:
    """Service to calculate utilization metrics using Gaussian-weighted scoring."""
    
    UTILIZATION_PARAMS = UtilizationConfig.DEFAULT_UTILIZATION_PARAMS
    BURN_DAYS_PARAMS = UtilizationConfig.DEFAULT_BURN_DAYS_PARAMS
    DAILY_SPEND_PARAMS = UtilizationConfig.DEFAULT_DAILY_SPEND_PARAMS
    LABEL_THRESHOLDS = UtilizationConfig.DEFAULT_LABEL_THRESHOLDS

    def __init__(
        self, 
        transactions: list[InternalTransaction], 
        paycheck_info: PaycheckInfo,
        config: Optional[UtilizationConfig] = None
    ):
        self.transactions = Normalization.normalize_and_sort_trxns(transactions)
        self.paycheck_info = paycheck_info
        self.config = config or UtilizationConfig()
        self.UTILIZATION_PARAMS = self.config.utilization_params
        self.BURN_DAYS_PARAMS = self.config.burn_days_params
        self.DAILY_SPEND_PARAMS = self.config.daily_spend_params
        self.LABEL_THRESHOLDS = self.config.label_thresholds

    @staticmethod
    def _gaussian_score(value: float, mu: float, sigma: float) -> float:
        if value is None:
            return 0.0
        exponent = -((value - mu) ** 2) / (2 * sigma ** 2)
        return math.exp(exponent)
    
    @staticmethod
    def _asymmetric_gaussian_score(value: float, mu: float, sigma_left: float, sigma_right: float) -> float:
        if value is None:
            return 0.0
        sigma = sigma_left if value <= mu else sigma_right
        exponent = -((value - mu) ** 2) / (2 * sigma ** 2)
        return math.exp(exponent)

    def _calculate_component_scores(
        self, 
        utilization: float, 
        burn_days: float, 
        daily_spend_ratio: float
    ) -> dict:
        util_mu, util_sigma, util_weight = self.UTILIZATION_PARAMS
        util_score = self._asymmetric_gaussian_score(
            utilization, mu=util_mu, sigma_left=0.5, sigma_right=0.25
        )
        
        burn_mu, burn_sigma, burn_weight = self.BURN_DAYS_PARAMS
        burn_score = self._asymmetric_gaussian_score(
            burn_days if burn_days else 0, mu=burn_mu, sigma_left=10.0, sigma_right=30.0
        )
        
        spend_mu, spend_sigma, spend_weight = self.DAILY_SPEND_PARAMS
        spend_score = self._gaussian_score(daily_spend_ratio, spend_mu, spend_sigma)
        
        return {
            "utilization_score": round(util_score, 3),
            "burn_days_score": round(burn_score, 3),
            "daily_spend_score": round(spend_score, 3),
            "weights": {
                "utilization": util_weight,
                "burn_days": burn_weight,
                "daily_spend": spend_weight
            }
        }

    def _calculate_composite_score(self, component_scores: dict) -> float:
        weights = component_scores["weights"]
        weighted_sum = (
            component_scores["utilization_score"] * weights["utilization"] +
            component_scores["burn_days_score"] * weights["burn_days"] +
            component_scores["daily_spend_score"] * weights["daily_spend"]
        )
        return round(weighted_sum * 100, 1)

    def _score_to_label(self, score: float) -> str:
        for threshold, label in self.LABEL_THRESHOLDS:
            if score >= threshold:
                return label
        return "critical-risk"

    def calculate(self) -> dict:
        if not self.paycheck_info or self.paycheck_info.paycheck_confidence < 0.3:
            return self._empty_result()

        avg_paycheck = self.paycheck_info.avg_paycheck_cents
        period_days = self.paycheck_info.period_days

        if not avg_paycheck or not period_days:
            return self._empty_result()

        last_day = self.transactions[-1].date
        start_cycle = last_day - timedelta(days=int(period_days))

        debits = [t for t in self.transactions if t.type == "debit" and t.date >= start_cycle]
        total_debits = sum(d.amount_cents for d in debits)

        utilization = total_debits / avg_paycheck if avg_paycheck > 0 else None
        days = max(1, (last_day - start_cycle).days)
        avg_daily_spend = total_debits / days if days > 0 else 0
        burn_days = avg_paycheck / avg_daily_spend if avg_daily_spend > 0 else None
        daily_spend_ratio = avg_daily_spend / avg_paycheck if avg_paycheck > 0 else 0

        component_scores = self._calculate_component_scores(
            utilization=utilization, burn_days=burn_days, daily_spend_ratio=daily_spend_ratio
        )
        composite_score = self._calculate_composite_score(component_scores)
        label = self._score_to_label(composite_score) if utilization is not None else "unknown"

        return {
            "utilization_pct": round(utilization, 3) if utilization is not None else None,
            "avg_daily_spend_cents": int(avg_daily_spend),
            "burn_days": round(burn_days, 1) if burn_days else None,
            "utilization_label": label,
            "composite_score": composite_score,
            "component_scores": component_scores,
            "cycle_start": start_cycle,
            "cycle_end": last_day,
        }

    def _empty_result(self) -> dict:
        return {
            "utilization_pct": None,
            "avg_daily_spend_cents": None,
            "burn_days": None,
            "utilization_label": "unknown",
            "composite_score": 0.0,
            "component_scores": None,
            "cycle_start": None,
            "cycle_end": None,
        }
