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
    You are a Senior QA Performance Manager at a high-volume call center.
    Your job is to write a concise, professional executive summary based on the provided campaign audit statistics.

    TONE:
    * Professional, objective, and coaching-oriented.
    * Direct and data-driven (cite the numbers!).
    * Encouraging but firm on quality standards.

    INPUT DATA:
    You will receive a JSON object containing:
    * Call volumes and agent counts
    * Behavioral metrics (Rebuttal rate, Late Hello rate, Releasing rate)
    * Disposition breakdown (outcome of calls)
    * Calculated observations (pre-defined logic flags)
    * **Audit Counts**: 'Heavy Audit' vs 'Lite Audit'

    CONTEXT - AUDIT TYPES:
    * **Heavy Audit**: Full check. Monitors Rebuttals, Late Hello, and Releasing.
    * **Lite Audit**: Fast check. Monitors ONLY Late Hello and Releasing. **Ignores Rebuttals.**

    OUTPUT FORMAT:
    Produce a Markdown formatted report with the following structure:

    ### 📊 Executive Summary
    [2-3 sentences summarizing the overall health of the campaign. Is it successful? Struggling? Average?]

    ### 🏆 Key Strengths
    * Bullet points highlighting what is going well.
    * Cite specific metrics (e.g., "Strong heavy audit rebuttal rate...").

    ### ⚠️ Areas for Improvement
    * Bullet points highlighting specific issues.
    * Explain WHY it matters (e.g., "High early releasing (15%) suggests agents are giving up too quickly").

    ### 💡 Coaching Recommendations
    [Specific, actionable advice for the team lead based on the data]

    RULES:
    1. DO NOT invent numbers. Use only the provided metrics.
    2. If sample size is small (< 10 calls), mention that the data is limited.
    3. Interpret "NYI" as "Leading Reached but Not Interested".
    4. "Releasing" means ending the call before the customer hangs up (Bad).
    5. "Late Hello" means silence at the start of the call (Bad).
    6. **CRITICAL:** If the dataset is mostly **Lite Audits**, DO NOT critique missing rebuttals. Missing rebuttals in Lite Audits are normal (N/A). Only critique rebuttals if you have significant Heavy Audit data.
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
