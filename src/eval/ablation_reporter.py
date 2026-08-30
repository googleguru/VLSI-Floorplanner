"""Enhanced ablation study reporting with per-rule breakdown and interaction analysis.

Generates:
  - Per-rule performance metrics
  - Rule interaction analysis  
  - Benefit/cost tradeoff matrix
  - Contribution scoring
"""
from __future__ import annotations

import dataclasses
from typing import Dict, List
import numpy as np


@dataclasses.dataclass
class RuleContribution:
    """Metrics for a single rule or configuration."""
    name:                 str
    hpwl_um:             float
    overlap_count:       int
    outline_success:     float
    density_variance:    float
    whitespace_frag:     float
    runtime_s:           float
    
    # Computed relative improvements (vs baseline)
    hpwl_improvement:    float = 0.0  # percentage, positive is better
    overlap_reduction:   float = 0.0  # percentage
    variance_reduction:  float = 0.0
    frag_reduction:      float = 0.0


@dataclasses.dataclass
class InteractionEffect:
    """Quantifies how two rules interact."""
    rule1:              str
    rule2:              str
    combined_hpwl:      float
    rule1_alone_hpwl:   float
    rule2_alone_hpwl:   float
    expected_hpwl:      float  # rule1 + rule2 improvement (linear estimate)
    synergy:            float  # (expected - combined) / expected; pos = synergistic


class AblationReporter:
    """Generate detailed ablation study reports."""
    
    def __init__(self, baseline_metrics: RuleContribution) -> None:
        """
        Args:
            baseline_metrics: Metrics from pure OpenROAD baseline (no CA)
        """
        self.baseline = baseline_metrics
    
    def compute_improvements(
        self,
        config_results: Dict[str, RuleContribution]
    ) -> Dict[str, RuleContribution]:
        """
        Compute relative improvements for all configurations vs baseline.
        
        Args:
            config_results: {config_name: metrics}
            
        Returns:
            Same dict with improvement percentages filled in
        """
        for config in config_results.values():
            # HPWL: negative values = improvement (lower is better)
            if self.baseline.hpwl_um > 0:
                config.hpwl_improvement = (
                    (self.baseline.hpwl_um - config.hpwl_um) / self.baseline.hpwl_um
                ) * 100.0
            
            # Overlaps: reduction is improvement
            if self.baseline.overlap_count > 0:
                config.overlap_reduction = (
                    (self.baseline.overlap_count - config.overlap_count) / 
                    self.baseline.overlap_count
                ) * 100.0
            else:
                config.overlap_reduction = 0.0 if config.overlap_count == 0 else -100.0
            
            # Variance: lower is better
            if self.baseline.density_variance > 0:
                config.variance_reduction = (
                    (self.baseline.density_variance - config.density_variance) /
                    self.baseline.density_variance
                ) * 100.0
            
            # Fragmentation: lower is better
            if self.baseline.whitespace_frag > 0:
                config.frag_reduction = (
                    (self.baseline.whitespace_frag - config.whitespace_frag) /
                    self.baseline.whitespace_frag
                ) * 100.0
        
        return config_results
    
    def analyze_interactions(
        self,
        single_rules: Dict[str, RuleContribution],
        paired_rules: Dict[str, RuleContribution],
    ) -> List[InteractionEffect]:
        """
        Analyze pairwise rule interactions.
        
        Args:
            single_rules: {rule_name: metrics}
            paired_rules: {rule1_rule2: metrics}
            
        Returns:
            List of interaction effects
        """
        effects = []
        
        # Expected pairs based on naming convention: "rule1_rule2"
        for pair_name, combined in paired_rules.items():
            parts = pair_name.split("_")
            if len(parts) < 2:
                continue
            
            rule1 = parts[0]
            rule2 = parts[1]
            
            if rule1 not in single_rules or rule2 not in single_rules:
                continue
            
            r1_alone = single_rules[rule1]
            r2_alone = single_rules[rule2]
            
            # Linear estimate: sum of individual improvements
            # But HPWL improvements need to account for baseline
            baseline_hpwl = self.baseline.hpwl_um
            r1_imp = (baseline_hpwl - r1_alone.hpwl_um)
            r2_imp = (baseline_hpwl - r2_alone.hpwl_um)
            expected_hpwl = baseline_hpwl - r1_imp - r2_imp
            
            # Synergy: how much better than linear combination?
            # Positive = synergistic, Negative = antagonistic
            if expected_hpwl != 0:
                synergy = (expected_hpwl - combined.hpwl_um) / abs(expected_hpwl)
            else:
                synergy = 0.0
            
            effects.append(InteractionEffect(
                rule1=rule1,
                rule2=rule2,
                combined_hpwl=combined.hpwl_um,
                rule1_alone_hpwl=r1_alone.hpwl_um,
                rule2_alone_hpwl=r2_alone.hpwl_um,
                expected_hpwl=expected_hpwl,
                synergy=synergy,
            ))
        
        return effects
    
    def rank_rules(
        self,
        results: Dict[str, RuleContribution]
    ) -> List[tuple]:
        """
        Rank single rules by HPWL improvement.
        
        Returns:
            List of (rule_name, hpwl_improvement, hpwl_um)
        """
        single_results = [
            (name, cfg) for name, cfg in results.items()
            if "single" in name and "only" in name
        ]
        
        # Sort by HPWL improvement (descending)
        ranked = sorted(
            single_results,
            key=lambda x: x[1].hpwl_improvement,
            reverse=True
        )
        
        return [(name, cfg.hpwl_improvement, cfg.hpwl_um) for name, cfg in ranked]
    
    def generate_report(
        self,
        results: Dict[str, RuleContribution],
        interactions: List[InteractionEffect],
    ) -> str:
        """Generate comprehensive ablation report."""
        lines = [
            "=" * 80,
            "ABLATION STUDY REPORT",
            "=" * 80,
            "",
            f"Baseline (no CA): HPWL={self.baseline.hpwl_um:.1f} µm, "
            f"Overlaps={self.baseline.overlap_count}",
            "",
        ]
        
        # Section 1: Per-rule rankings
        lines.extend([
            "SECTION 1: SINGLE-RULE PERFORMANCE",
            "-" * 80,
        ])
        
        ranked = self.rank_rules(results)
        for i, (rule, improvement, hpwl) in enumerate(ranked, 1):
            rule_clean = rule.replace("single_", "").replace("_only", "")
            lines.append(
                f"{i}. {rule_clean:25s}: HPWL={hpwl:7.1f} µm "
                f"({improvement:+6.1f}% vs baseline)"
            )
        
        lines.extend(["", ""])
        
        # Section 2: Complete configurations
        lines.extend([
            "SECTION 2: COMPLETE CONFIGURATIONS",
            "-" * 80,
        ])
        
        config_order = ["baseline", "density_only", "density_connectivity", "full_ca"]
        for config in config_order:
            if config in results:
                cfg = results[config]
                lines.append(
                    f"{config:25s}: HPWL={cfg.hpwl_um:7.1f} µm "
                    f"({cfg.hpwl_improvement:+6.1f}%), "
                    f"Overlaps={cfg.overlap_count}, "
                    f"Runtime={cfg.runtime_s:.2f}s"
                )
        
        lines.extend(["", ""])
        
        # Section 3: Interaction analysis
        if interactions:
            lines.extend([
                "SECTION 3: RULE INTERACTIONS",
                "-" * 80,
                "Synergy > 0 = rules work better together (synergistic)",
                "Synergy < 0 = rules interfere (antagonistic)",
                "",
            ])
            
            # Sort by synergy magnitude
            sorted_int = sorted(interactions, key=lambda x: abs(x.synergy), reverse=True)
            
            for effect in sorted_int:
                syn_sign = "+" if effect.synergy > 0 else ""
                lines.append(
                    f"{effect.rule1:15s} + {effect.rule2:15s}: "
                    f"Synergy={syn_sign}{effect.synergy:+.3f} "
                    f"(combined={effect.combined_hpwl:.1f}, "
                    f"expected={effect.expected_hpwl:.1f})"
                )
        
        lines.extend(["", ""])
        
        # Section 4: Metrics comparison table
        lines.extend([
            "SECTION 4: FULL METRICS TABLE",
            "-" * 80,
            f"{'Config':<25} {'HPWL (µm)':<12} {'Overlaps':<10} {'Var Reduction':<15} {'Frag Reduction':<15}",
            "-" * 80,
        ])
        
        for name in sorted(results.keys()):
            cfg = results[name]
            lines.append(
                f"{name:<25} {cfg.hpwl_um:>10.1f}   {cfg.overlap_count:>8} "
                f"{cfg.variance_reduction:>13.1f}%  {cfg.frag_reduction:>13.1f}%"
            )
        
        lines.extend([
            "=" * 80,
        ])
        
        return "\n".join(lines)
    
    def benefit_cost_analysis(
        self,
        results: Dict[str, RuleContribution]
    ) -> str:
        """Analyze benefit/cost tradeoff: HPWL improvement vs runtime."""
        lines = [
            "=" * 80,
            "BENEFIT/COST ANALYSIS",
            "=" * 80,
            "",
            "Benefit = HPWL improvement (%), Cost = Runtime increase (s)",
            "Efficiency = Benefit / Cost  (higher is better)",
            "",
            f"{'Config':<25} {'Benefit':<12} {'Cost (s)':<12} {'Efficiency':<12}",
            "-" * 80,
        ]
        
        for name in sorted(results.keys()):
            cfg = results[name]
            cost = cfg.runtime_s - self.baseline.runtime_s
            if cost > 0:
                efficiency = cfg.hpwl_improvement / cost
            else:
                efficiency = float('inf') if cfg.hpwl_improvement > 0 else 0.0
            
            lines.append(
                f"{name:<25} {cfg.hpwl_improvement:>10.1f}%  "
                f"{cost:>10.2f}s   {efficiency:>10.1f}"
            )
        
        lines.extend(["=" * 80])
        
        return "\n".join(lines)


if __name__ == "__main__":
    # Example usage
    baseline = RuleContribution(
        name="baseline",
        hpwl_um=1000.0,
        overlap_count=5,
        outline_success=1.0,
        density_variance=0.15,
        whitespace_frag=0.8,
        runtime_s=1.0,
    )
    
    reporter = AblationReporter(baseline)
    
    # Simulate some results
    results = {
        "baseline": baseline,
        "single_density_only": RuleContribution(
            name="single_density_only",
            hpwl_um=950.0,
            overlap_count=4,
            outline_success=1.0,
            density_variance=0.12,
            whitespace_frag=0.7,
            runtime_s=1.5,
        ),
        "single_connectivity_only": RuleContribution(
            name="single_connectivity_only",
            hpwl_um=880.0,
            overlap_count=3,
            outline_success=1.0,
            density_variance=0.10,
            whitespace_frag=0.65,
            runtime_s=1.6,
        ),
    }
    
    reporter.compute_improvements(results)
    
    print(reporter.generate_report(results, []))
    print("\n")
    print(reporter.benefit_cost_analysis(results))
