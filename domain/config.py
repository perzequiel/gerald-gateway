"""
Configuration module for BNPL Risk Scoring System.

All configuration values are loaded from environment variables with sensible defaults.
See .env.example for all available configuration options.
"""
import os
from dataclasses import dataclass
from typing import List, Tuple


def _get_float(key: str, default: float) -> float:
    """Get float from environment variable."""
    return float(os.getenv(key, default))


def _get_int(key: str, default: int) -> int:
    """Get int from environment variable."""
    return int(os.getenv(key, default))


@dataclass
class BNPLTierConfig:
    """BNPL tier limits and score thresholds."""
    
    # Tier limits in cents
    tier_a_limit: int = _get_int("BNPL_TIER_A_LIMIT", 20000)  # $200
    tier_b_limit: int = _get_int("BNPL_TIER_B_LIMIT", 12000)  # $120
    tier_c_limit: int = _get_int("BNPL_TIER_C_LIMIT", 6000)   # $60
    tier_d_limit: int = _get_int("BNPL_TIER_D_LIMIT", 2000)   # $20
    
    # Minimum scores for tiers
    tier_a_min_score: float = _get_float("BNPL_TIER_A_MIN_SCORE", 75.0)
    tier_b_min_score: float = _get_float("BNPL_TIER_B_MIN_SCORE", 55.0)
    tier_c_min_score: float = _get_float("BNPL_TIER_C_MIN_SCORE", 35.0)
    # Tier D has no minimum - it's the fallback


@dataclass
class RiskWeightsConfig:
    """Risk calculation weights and penalties."""
    
    # Component weights (must sum to 1.0)
    balance_weight: float = _get_float("RISK_BALANCE_WEIGHT", 0.5)
    income_spend_weight: float = _get_float("RISK_INCOME_SPEND_WEIGHT", 0.3)
    nsf_weight: float = _get_float("RISK_NSF_WEIGHT", 0.2)
    
    # Penalties
    balance_neg_cap: int = _get_int("RISK_BALANCE_NEG_CAP", 10000)
    nsf_penalty: float = _get_float("RISK_NSF_PENALTY", 25.0)
    payback_penalty: float = _get_float("RISK_PAYBACK_PENALTY", 10.0)
    
    # Utilization penalties
    util_penalty_high_risk: float = _get_float("UTIL_PENALTY_HIGH_RISK", 15.0)
    util_penalty_medium_risk: float = _get_float("UTIL_PENALTY_MEDIUM_RISK", 7.5)


@dataclass  
class UtilizationConfig:
    """Gaussian scoring parameters for utilization analysis."""
    
    # Utilization params (mu, sigma, weight)
    util_mu: float = _get_float("UTIL_MU", 0.6)
    util_sigma: float = _get_float("UTIL_SIGMA", 0.3)
    util_weight: float = _get_float("UTIL_WEIGHT", 0.45)
    
    # Burn days params
    burn_mu: float = _get_float("BURN_MU", 30.0)
    burn_sigma: float = _get_float("BURN_SIGMA", 15.0)
    burn_weight: float = _get_float("BURN_WEIGHT", 0.35)
    
    # Daily spend params
    spend_mu: float = _get_float("SPEND_MU", 0.033)
    spend_sigma: float = _get_float("SPEND_SIGMA", 0.02)
    spend_weight: float = _get_float("SPEND_WEIGHT", 0.20)
    
    # Label thresholds
    label_healthy: int = _get_int("LABEL_HEALTHY", 80)
    label_medium_risk: int = _get_int("LABEL_MEDIUM_RISK", 60)
    label_high_risk: int = _get_int("LABEL_HIGH_RISK", 40)
    label_very_high_risk: int = _get_int("LABEL_VERY_HIGH_RISK", 20)
    
    def get_utilization_params(self) -> Tuple[float, float, float]:
        """Return utilization params as tuple (mu, sigma, weight)."""
        return (self.util_mu, self.util_sigma, self.util_weight)
    
    def get_burn_days_params(self) -> Tuple[float, float, float]:
        """Return burn days params as tuple (mu, sigma, weight)."""
        return (self.burn_mu, self.burn_sigma, self.burn_weight)
    
    def get_daily_spend_params(self) -> Tuple[float, float, float]:
        """Return daily spend params as tuple (mu, sigma, weight)."""
        return (self.spend_mu, self.spend_sigma, self.spend_weight)
    
    def get_label_thresholds(self) -> List[Tuple[int, str]]:
        """Return label thresholds as list of (threshold, label) tuples."""
        return [
            (self.label_healthy, "healthy"),
            (self.label_medium_risk, "medium-risk"),
            (self.label_high_risk, "high-risk"),
            (self.label_very_high_risk, "very-high-risk"),
            (0, "critical-risk"),
        ]


@dataclass
class CooldownConfig:
    """Cooldown settings."""
    cooldown_hours: int = _get_int("COOLDOWN_HOURS", 72)


# Global config instances (lazy loaded)
_bnpl_config = None
_risk_config = None
_util_config = None
_cooldown_config = None


def get_bnpl_config() -> BNPLTierConfig:
    """Get BNPL tier configuration."""
    global _bnpl_config
    if _bnpl_config is None:
        _bnpl_config = BNPLTierConfig()
    return _bnpl_config


def get_risk_config() -> RiskWeightsConfig:
    """Get risk weights configuration."""
    global _risk_config
    if _risk_config is None:
        _risk_config = RiskWeightsConfig()
    return _risk_config


def get_util_config() -> UtilizationConfig:
    """Get utilization configuration."""
    global _util_config
    if _util_config is None:
        _util_config = UtilizationConfig()
    return _util_config


def get_cooldown_config() -> CooldownConfig:
    """Get cooldown configuration."""
    global _cooldown_config
    if _cooldown_config is None:
        _cooldown_config = CooldownConfig()
    return _cooldown_config


def reload_config():
    """Force reload of all configuration from environment variables."""
    global _bnpl_config, _risk_config, _util_config, _cooldown_config
    _bnpl_config = BNPLTierConfig()
    _risk_config = RiskWeightsConfig()
    _util_config = UtilizationConfig()
    _cooldown_config = CooldownConfig()

