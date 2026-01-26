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
    You are a Senior QA Performance Manager. Your job is to generate a comprehensive Performance Audit Report.
    
    INPUT DATA:
    You will receive JSON with metric_summaries (Good/Bad counts), quality_score_distribution, agent_performance_details, and audit_counts.

    OUTPUT FORMAT - YOU MUST FOLLOW THIS EXACT STRUCTURE:

    # Performance Audit Report
    **Report Date:** [Today's Date]  
    **Audit Period:** [Date Range from input data]  
    **Total Calls Reviewed:** [Total from data]  
    **Overall Team Performance:** [Average Quality Score]%

    ---

    ## EXECUTIVE SUMMARY

    [Write 3-4 sentences mentioning:
    - Overall performance trend
    - Specific agents doing well (name them)
    - Specific agents struggling (name them with their issues)
    - Main team-wide problem with percentage]

    Example: "Most agents are doing the basics correctly - starting calls on time and confirming who they're talking to. However, **2 agents (Nurhan and Radwa) are struggling with basic requirements** like introducing themselves. Also, about **38% of agents are skipping rebuttals** when they should be using them."

    ---

    ## PERFORMANCE METRICS

    ### **1. Late Hello**
    **Target:** 0% | **Actual:** [Bad%]% | **Status:** [✓ or ⚠️ or ✗]

    | Result | Count | Percentage |
    |--------|-------|------------|
    | No (Good) | [Count] | [%]% |
    | Yes (Bad) | [Count] | [%]% |

    [One sentence comment about what this means]

    ---

    ### **2. Early Call Release**
    **Target:** <5% | **Actual:** [Bad%]% | **Status:** [✓ or ⚠️ or ✗]

    | Result | Count | Percentage |
    |--------|-------|------------|
    | No (Good) | [Count] | [%]% |
    | Yes (Bad) | [Count] | [%]% |

    [One sentence comment]

    ---

    ### **3. Rebuttal Usage**
    **Target:** >90% | **Actual:** [Good%]% | **Status:** [✓ or ⚠️ or ✗]

    | Result | Count | Percentage |
    |--------|-------|------------|
    | Yes (Good - Used Rebuttals) | [Count] | [%]% |
    | No (Bad - Skipped Rebuttals) | [Count] | [%]% |

    **[X] out of [Total] calls had NO rebuttals.** [Explain what this means - e.g., "These agents are giving up too easily"]

    *(If mostly Lite Audits: write "Not Measured - Lite Audits don't check rebuttals" instead of table)*

    ---

    ### **4. Owner Name Confirmation**
    **Target:** 95% | **Actual:** [Good%]% | **Status:** [✓ or ⚠️ or ✗]

    | Result | Count | Percentage |
    |--------|-------|------------|
    | Yes (Good) | [Count] | [%]% |
    | No (Bad) | [Count] | [%]% |

    [One sentence comment]

    ---

    ### **5. Agent Introduction**
    **Target:** 95% | **Actual:** [Good%]% | **Status:** [✓ or ⚠️ or ✗]

    | Result | Count | Percentage |
    |--------|-------|------------|
    | Yes (Good) | [Count] | [%]% |
    | No (Bad) | [Count] | [%]% |

    [One sentence comment]

    ---

    ### **6. Reason for Calling**
    **Target:** 95% | **Actual:** [Good%]% | **Status:** [✓ or ⚠️ or ✗]

    | Result | Count | Percentage |
    |--------|-------|------------|
    | Yes (Good) | [Count] | [%]% |
    | No (Bad) | [Count] | [%]% |

    [One sentence comment]

    ---

    CRITICAL RULES:
    1. **YOU MUST INCLUDE ALL 6 METRICS** - Do not skip any tables
    2. **USE EXACT NUMBERS** from the JSON data - never invent counts
    3. **NAME SPECIFIC AGENTS** in Executive Summary (extract from agent_performance_details)
    4. Status: 0% Bad = "✓ EXCELLENT", ≤10% = "✓ GOOD", ≤30% = "⚠️ NEEDS IMPROVEMENT", >30% = "✗ CRITICAL"
    5. For Lite Audits: Skip Rebuttal/Intro/Reason/Owner tables and write "Not Measured"
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
