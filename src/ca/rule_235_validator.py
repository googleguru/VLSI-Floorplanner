"""Rule 235 validation and analysis module.

Provides tools to measure the effect of Wolfram Rule 235 on density distributions:
  - Before/after island count
  - Before/after fragmentation metrics
  - Isolated cell detection
  - Birth/survival statistics
  - Connectivity analysis
"""
from __future__ import annotations

import dataclasses
import logging
from typing import Tuple, List

import numpy as np
from scipy.ndimage import label as ndi_label

log = logging.getLogger(__name__)


@dataclasses.dataclass
class IslandMetrics:
    """Metrics on connected density regions (islands)."""
    num_islands:         int
    island_sizes:        List[int]   # size of each island (# cells)
    mean_island_size:    float
    max_island_size:     int
    num_isolated_cells:  int
    fragmentation_score: float       # higher = more fragmented


@dataclasses.dataclass
class Rule235Metrics:
    """Before/after metrics for Rule 235 application."""
    pre_metrics:          IslandMetrics
    post_metrics:         IslandMetrics
    islands_eliminated:   int
    isolated_cells_found: int
    cells_born:           int
    cells_died:           int
    connectivity_improvement: float  # 0 to 1; 1 = perfect improvement


class Rule235Validator:
    """Analyze Rule 235 effects on density distributions."""

    def __init__(self, threshold: float = 0.30) -> None:
        self.threshold = threshold

    def measure_islands(self, density: np.ndarray) -> IslandMetrics:
        """Identify connected components (islands) in density field."""
        # Binary active map
        active = (density >= self.threshold).astype(np.uint8)

        # Label connected components (Moore connectivity)
        labeled_array, num_features = ndi_label(active)

        if num_features == 0:
            return IslandMetrics(
                num_islands=0,
                island_sizes=[],
                mean_island_size=0.0,
                max_island_size=0,
                num_isolated_cells=0,
                fragmentation_score=0.0,
            )

        # Get sizes of each island
        island_sizes = []
        for label_id in range(1, num_features + 1):
            size = np.sum(labeled_array == label_id)
            island_sizes.append(size)

        # Count isolated cells (size=1 islands)
        isolated_count = sum(1 for size in island_sizes if size == 1)

        # Fragmentation score: based on density variance within regions
        # Higher score = more fragmented
        active_cells = np.sum(active)
        if active_cells == 0:
            frag_score = 0.0
        else:
            # Size disparity metric
            sizes_arr = np.array(island_sizes, dtype=np.float32)
            if len(sizes_arr) > 1:
                size_variance = np.var(sizes_arr)
                frag_score = float(np.sqrt(size_variance) / (np.mean(sizes_arr) + 1e-6))
            else:
                frag_score = 0.0

        return IslandMetrics(
            num_islands=num_features,
            island_sizes=island_sizes,
            mean_island_size=float(np.mean(island_sizes)) if island_sizes else 0.0,
            max_island_size=max(island_sizes) if island_sizes else 0,
            num_isolated_cells=isolated_count,
            fragmentation_score=frag_score,
        )

    def detect_rule235_effects(
        self,
        density_pre: np.ndarray,
        density_post: np.ndarray,
        threshold: float = None,
    ) -> Rule235Metrics:
        """Measure before/after effects of Rule 235."""
        if threshold is None:
            threshold = self.threshold

        # Binary maps
        active_pre = (density_pre >= threshold).astype(np.float32)
        active_post = (density_post >= threshold).astype(np.float32)

        # Island metrics
        pre_metrics = self.measure_islands(density_pre)
        post_metrics = self.measure_islands(density_post)

        # Count cells that changed state
        cells_born = np.sum((active_pre < 0.5) & (active_post >= 0.5))
        cells_died = np.sum((active_pre >= 0.5) & (active_post < 0.5))

        islands_eliminated = max(0, pre_metrics.num_islands - post_metrics.num_islands)

        # Connectivity improvement: how much did the largest connected component grow?
        max_pre = pre_metrics.max_island_size
        max_post = post_metrics.max_island_size
        if max_pre > 0:
            connectivity_improvement = min(1.0, float(max_post - max_pre) / max_pre)
        else:
            connectivity_improvement = 0.0 if max_post == 0 else 1.0

        return Rule235Metrics(
            pre_metrics=pre_metrics,
            post_metrics=post_metrics,
            islands_eliminated=islands_eliminated,
            isolated_cells_found=pre_metrics.num_isolated_cells,
            cells_born=int(cells_born),
            cells_died=int(cells_died),
            connectivity_improvement=connectivity_improvement,
        )

    def find_isolated_cells(self, density: np.ndarray) -> np.ndarray:
        """Return binary mask of isolated cells (size-1 islands)."""
        active = (density >= self.threshold).astype(np.uint8)
        labeled_array, num_features = ndi_label(active)

        isolated_mask = np.zeros_like(active, dtype=np.uint8)
        for label_id in range(1, num_features + 1):
            island_mask = (labeled_array == label_id)
            if np.sum(island_mask) == 1:
                isolated_mask |= island_mask

        return isolated_mask.astype(np.float32)

    def find_birth_cells(
        self,
        density_pre: np.ndarray,
        density_post: np.ndarray,
    ) -> np.ndarray:
        """Return binary mask of cells where density transitioned from <threshold to ≥threshold."""
        active_pre = (density_pre < self.threshold).astype(np.uint8)
        active_post = (density_post >= self.threshold).astype(np.uint8)
        
        births = (active_pre > 0) & (active_post > 0)
        return births.astype(np.float32)

    def report(self, metrics: Rule235Metrics) -> str:
        """Generate a human-readable report."""
        lines = [
            "=" * 70,
            "RULE 235 VALIDATION REPORT",
            "=" * 70,
            "",
            "PRE-APPLICATION METRICS:",
            f"  Islands:               {metrics.pre_metrics.num_islands}",
            f"  Isolated cells:        {metrics.pre_metrics.num_isolated_cells}",
            f"  Mean island size:      {metrics.pre_metrics.mean_island_size:.2f} cells",
            f"  Max island size:       {metrics.pre_metrics.max_island_size}",
            f"  Fragmentation score:   {metrics.pre_metrics.fragmentation_score:.4f}",
            "",
            "POST-APPLICATION METRICS:",
            f"  Islands:               {metrics.post_metrics.num_islands}",
            f"  Isolated cells:        {metrics.post_metrics.num_isolated_cells}",
            f"  Mean island size:      {metrics.post_metrics.mean_island_size:.2f} cells",
            f"  Max island size:       {metrics.post_metrics.max_island_size}",
            f"  Fragmentation score:   {metrics.post_metrics.fragmentation_score:.4f}",
            "",
            "CHANGES:",
            f"  Islands eliminated:    {metrics.islands_eliminated}",
            f"  Cells born:            {metrics.cells_born}",
            f"  Cells died:            {metrics.cells_died}",
            f"  Connectivity gain:     {metrics.connectivity_improvement:.2%}",
            "",
            "EFFECTIVENESS:",
        ]

        if metrics.pre_metrics.num_isolated_cells > 0:
            elim_rate = (
                metrics.isolated_cells_found / 
                metrics.pre_metrics.num_isolated_cells
            )
            lines.append(f"  Isolated cell removal: {elim_rate:.1%}")
        else:
            lines.append("  Isolated cell removal: N/A (none found)")

        if metrics.pre_metrics.num_islands > 0:
            elim_rate = metrics.islands_eliminated / metrics.pre_metrics.num_islands
            lines.append(f"  Island reduction:      {elim_rate:.1%}")
        else:
            lines.append("  Island reduction:      N/A (no islands)")

        lines.extend([
            "=" * 70,
        ])

        return "\n".join(lines)


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)
    
    # Create synthetic test density with islands
    test_den = np.random.random((64, 64)).astype(np.float32) * 0.2
    # Add some islands
    test_den[10:15, 10:15] = 0.5  # big island
    test_den[20, 20] = 0.5        # isolated cell
    test_den[40:42, 40:42] = 0.4  # medium island
    
    validator = Rule235Validator(threshold=0.30)
    pre_metrics = validator.measure_islands(test_den)
    print(f"Pre: {pre_metrics.num_islands} islands, {pre_metrics.num_isolated_cells} isolated")
    
    # Simulate post-Rule235 (eliminate isolated, connect nearby)
    test_den_post = test_den.copy()
    test_den_post[20, 20] = 0.0  # isolated cell dies
    test_den_post[40:45, 40:45] = 0.5  # medium becomes connected
    
    metrics = validator.detect_rule235_effects(test_den, test_den_post)
    print(validator.report(metrics))
