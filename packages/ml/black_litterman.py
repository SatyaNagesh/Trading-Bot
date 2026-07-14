"""Black-Litterman portfolio allocation model."""

import numpy as np

from packages.core.logging import get_logger

logger = get_logger("black_litterman")


def implied_returns(cov_matrix: np.ndarray, market_weights: np.ndarray, risk_aversion: float = 2.5) -> np.ndarray:
    return risk_aversion * cov_matrix @ market_weights


def black_litterman_allocate(
    cov_matrix: np.ndarray,
    market_weights: np.ndarray,
    views: dict[int, tuple[float, float]],
    tau: float = 0.05,
    risk_aversion: float = 2.5,
    delta: float = 0.01,
) -> dict:
    n = len(market_weights)
    pi = implied_returns(cov_matrix, market_weights, risk_aversion)
    P = np.zeros((len(views), n))
    Q = np.zeros(len(views))
    omega = np.zeros((len(views), len(views)))
    for i, (asset_idx, (return_view, uncertainty)) in enumerate(views.items()):
        P[i, asset_idx] = 1
        Q[i] = return_view
        omega[i, i] = uncertainty ** 2
    tau_sigma = tau * cov_matrix
    inv_tau_sigma = np.linalg.inv(tau_sigma)
    inv_omega = np.linalg.inv(omega)
    post_var = np.linalg.inv(inv_tau_sigma + P.T @ inv_omega @ P)
    post_mean = post_var @ (inv_tau_sigma @ pi + P.T @ inv_omega @ Q)
    weights = post_mean.flatten() / delta
    weights = weights / np.sum(np.abs(weights))
    return {
        "implied_returns": pi.tolist(),
        "posterior_returns": post_mean.flatten().tolist(),
        "weights": weights.tolist(),
        "n_assets": n,
        "n_views": len(views),
    }
