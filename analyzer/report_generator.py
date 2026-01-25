"""
LLM-Based Campaign Report Generator.
Transforms structured campaign metrics into a professional human-readable narrative.
"""

import logging
import json
from typing import Dict, Any, Optional
from analyzer.llm_rebuttal_evaluator import GroqClient

logger = logging.getLogger(__name__)

class CampaignReportGenerator:
    """Generates narrative campaign reports using GroqCloud LLM."""
    
    SYSTEM_PROMPT = """ROLE:
    You are a Senior QA Performance Manager. Your job is to generate a comprehensive Performance Audit Report based on the provided campaign data.
    
    INPUT DATA:
    You will receive a JSON object with:
    1. 'metric_summaries': Counts and percentages for each metric (Good/Bad).
    2. 'quality_score_distribution': Counts of calls at each score level (100%, 83%, etc.).
    3. 'agent_performance_details': Detailed stats per agent (failures, averages).
    4. 'audit_counts': Heavy vs Lite audit context.

    OUTPUT FORMAT:
    You MUST output Markdown that matches this structure exactly:

    # Performance Audit Report
    **Report Date:** [Current Date]
    **Total Calls Reviewed:** [Total Count]
    **Overall Team Performance:** [Average Score]%

    ## EXECUTIVE SUMMARY
    [2-3 sentences. Mention top performing agents, struggling agents, and biggest team-wide issue.]

    ## PERFORMANCE METRICS

    ### 1. Late Hello
    **Target:** 0% | **Actual:** [Bad Score]% | **Status:** [See Criteria]
    | Result | Count | Percentage |
    |--------|-------|------------|
    | No (Good) | [Count] | [%] |
    | Yes (Bad) | [Count] | [%] |
    *[One sentence comment]*

    ### 2. Early Call Release
    **Target:** <5% | **Actual:** [Bad Score]% | **Status:** [See Criteria]
    | Result | Count | Percentage |
    |--------|-------|------------|
    | No (Good) | [Count] | [%] |
    | Yes (Bad) | [Count] | [%] |

    ### 3. Rebuttal Usage
    **Target:** >90% | **Actual:** [Usage Score]% | **Status:** [See Criteria]
    | Result | Count | Percentage |
    |--------|-------|------------|
    | Yes (Good) | [Count] | [%] |
    | No (Bad) | [Count] | [%] |
    *(If Lite Audit: Mark as "Not Measured")*

    ### 4. Owner Name Confirmation
    **Target:** 95% | **Actual:** [Success Score]% | **Status:** [See Criteria]
    | Result | Count | Percentage |
    |--------|-------|------------|
    | Yes (Good) | [Count] | [%] |
    | No (Bad) | [Count] | [%] |

    ### 5. Agent Introduction
    **Target:** 95% | **Actual:** [Success Score]% | **Status:** [See Criteria]
    | Result | Count | Percentage |
    |--------|-------|------------|
    | Yes (Good) | [Count] | [%] |
    | No (Bad) | [Count] | [%] |

    ### 6. Reason for Calling
    **Target:** 95% | **Actual:** [Success Score]% | **Status:** [See Criteria]
    | Result | Count | Percentage |
    |--------|-------|------------|
    | Yes (Good) | [Count] | [%] |
    | No (Bad) | [Count] | [%] |

    ## QUALITY SCORE DISTRIBUTION
    | Score | Rating | Count | Percentage |
    |-------|--------|-------|------------|
    [Fill rows from quality_score_distribution]
    **Average Quality Score:** [Avg]%

    ## AGENT PERFORMANCE SUMMARY

    ### 🚨 NEEDS IMMEDIATE ATTENTION
    [List agents with ≥40% failure rate on ANY metric OR any score <= 33%]
    
    **[Agent Name]** | [Call Count] calls | Average: [Score]%
    **What's wrong:**
    - [Specific failure points, e.g., "Skipped rebuttals on 4 calls (44%)"]
    **What's good:**
    - [Success points]
    **What this means:** [One sentence coaching verdict]

    ### ⚠️ DOING OKAY BUT NEEDS IMPROVEMENT
    [List agents with 20-39% failure rates on any metric]
    *(Format same as above)*

    ### ✓ DOING WELL
    [List agents with <20% failures]
    *(Format same as above)*

    ## WHAT NEEDS TO HAPPEN NOW
    **Immediate Actions:**
    1. [Specific action for Problem Agent 1]
    2. [Specific action for Problem Agent 2]
    3. [Team-wide training recommendation]
    
    CRITERIA:
    * Status Logic: 
      - Bad% = 0% → "✓ EXCELLENT"
      - Bad% ≤ 10% → "✓ GOOD"
      - Bad% ≤ 30% → "⚠️ NEEDS IMPROVEMENT"
      - Bad% > 30% → "✗ CRITICAL PROBLEM"
    * Lite Audit Rule: If mostly Lite Audits, mark Rebuttals/Intro/Reason/Owner columns as "Not Measured" in tables.
    """

    def __init__(self):
        """Initialize with existing GroqClient logic."""
        try:
            self.client = GroqClient()
        except Exception as e:
            logger.error(f"Failed to initialize GroqClient for reports: {e}")
            self.client = None

    def generate_report(self, metrics: Dict[str, Any]) -> str:
        """
        Generate a markdown narrative from campaign metrics.
        
        Args:
            metrics: Dictionary of calculated stats (from dashboard_manager)
            
        Returns:
            Markdown string containing the report.
        """
        if not self.client:
            return "⚠️ AI Report Generation Unavailable (GroqClient failed to initialize)."

        try:
            # Prepare context for the LLM
            context_str = json.dumps(metrics, indent=2, default=str)
            
            user_prompt = f"""
            Analyze the following campaign data and write a performance report:
            
            DATA:
            {context_str}
            
            Write the report in Markdown.
            """

            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ]

            logger.info("Generating AI Campaign Report...")
            # Request non-JSON output for Markdown formatting
            response = self.client.create_completion(messages, retry_attempts=2, json_mode=False)
            
            # Extract content
            report_content = response['choices'][0]['message']['content']
            return report_content

        except Exception as e:
            logger.error(f"Error generating campaign report: {e}")
            return f"⚠️ Error generating report: {str(e)}"
