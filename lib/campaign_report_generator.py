"""
LLM-Powered Campaign Performance Report Generator (Restructured)
Uses Groq (llama-3.1-8b-instant) to generate comprehensive campaign analysis with tables.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)


class CampaignReportGenerator:
    """Generates detailed AI-powered campaign performance reports using Groq LLM."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.1-8b-instant"):
        """
        Initialize campaign report generator.
        
        Args:
            api_key: Groq API key (reads from GROQ_API_KEY env if not provided)
            model: Model to use (default: llama-3.1-8b-instant)
        """
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is required")
        
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        logger.info(f"CampaignReportGenerator initialized with model: {model}")
    
    def _call_groq_api(self, messages: List[Dict[str, str]], max_tokens: int = 3000) -> str:
        """Call Groq API and return response text."""
        import requests
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,  # Lower temperature for consistent analysis
            "max_tokens": max_tokens
        }
        
        try:
            response = requests.post(self.base_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"Groq API call failed: {e}")
            raise
    
    def _analyze_campaign_data(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate comprehensive campaign metrics for LLM analysis."""
        if df.empty:
            return {}
        
        total_calls = len(df)
        unique_agents = df['Agent Name'].nunique() if 'Agent Name' in df.columns else 0
        
        # Overall KPIs
        late_hello_bad = 0
        late_hello_good = total_calls
        releasing_bad = 0
        releasing_good = total_calls
        rebuttal_bad = 0
        rebuttal_good = total_calls
        
        if 'Late Hello Detection' in df.columns:
            late_hello_bad = len(df[df['Late Hello Detection'] == 'Yes'])
            late_hello_good = total_calls - late_hello_bad
        
        if 'Releasing Detection' in df.columns:
            releasing_bad = len(df[df['Releasing Detection'] == 'Yes'])
            releasing_good = total_calls - releasing_bad
        
        if 'Rebuttal Detection' in df.columns:
            rebuttal_bad = len(df[df['Rebuttal Detection'] == 'No'])
            rebuttal_good = total_calls - rebuttal_bad
        
        # Calculate percentages
        late_hello_pct = (late_hello_good / total_calls * 100) if total_calls > 0 else 0
        releasing_pct = (releasing_good / total_calls * 100) if total_calls > 0 else 0
        rebuttal_pct = (rebuttal_good / total_calls * 100) if total_calls > 0 else 0
        
        # Agent-level analysis
        agent_metrics = []
        
        if 'Agent Name' in df.columns:
            for agent in df['Agent Name'].unique():
                agent_df = df[df['Agent Name'] == agent]
                agent_calls = len(agent_df)
                
                agent_late_hello_bad = 0
                agent_releasing_bad = 0
                agent_rebuttal_bad = 0
                avg_intro_score = 0
                common_status = "N/A"
                
                if 'Late Hello Detection' in df.columns:
                    agent_late_hello_bad = len(agent_df[agent_df['Late Hello Detection'] == 'Yes'])
                
                if 'Releasing Detection' in df.columns:
                    agent_releasing_bad = len(agent_df[agent_df['Releasing Detection'] == 'Yes'])
                
                if 'Rebuttal Detection' in df.columns:
                    agent_rebuttal_bad = len(agent_df[agent_df['Rebuttal Detection'] == 'No'])
                
                if 'Intro Score' in df.columns:
                    try:
                        # Handle percentage strings
                        scores = agent_df['Intro Score'].astype(str).str.replace('%', '').astype(float)
                        avg_intro_score = scores.mean()
                    except:
                        avg_intro_score = 0
                
                if 'Status' in df.columns:
                    try:
                        common_status = agent_df['Status'].mode()[0]
                    except:
                        common_status = "N/A"
                
                # Calculate performance score (weighted)
                performance_score = 0
                if agent_calls > 0:
                    late_hello_score = ((agent_calls - agent_late_hello_bad) / agent_calls * 100) * 0.3
                    releasing_score = ((agent_calls - agent_releasing_bad) / agent_calls * 100) * 0.3
                    rebuttal_score = ((agent_calls - agent_rebuttal_bad) / agent_calls * 100) * 0.4
                    performance_score = late_hello_score + releasing_score + rebuttal_score
                
                agent_metrics.append({
                    'name': agent,
                    'total_calls': agent_calls,
                    'late_hello_bad': agent_late_hello_bad,
                    'releasing_bad': agent_releasing_bad,
                    'rebuttal_bad': agent_rebuttal_bad,
                    'avg_intro_score': round(avg_intro_score, 2),
                    'common_status': common_status,
                    'performance_score': round(performance_score, 2)
                })
            
            # Sort by performance score
            agent_metrics = sorted(agent_metrics, key=lambda x: x['performance_score'], reverse=True)
        
        return {
            'total_calls': total_calls,
            'unique_agents': unique_agents,
            'kpis': {
                'late_hello': {
                    'good': late_hello_good,
                    'bad': late_hello_bad,
                    'pct_good': round(late_hello_pct, 1)
                },
                'releasing': {
                    'good': releasing_good,
                    'bad': releasing_bad,
                    'pct_good': round(releasing_pct, 1)
                },
                'rebuttal': {
                    'good': rebuttal_good,
                    'bad': rebuttal_bad,
                    'pct_good': round(rebuttal_pct, 1)
                }
            },
            'agent_metrics': agent_metrics
        }
    
    def _build_analysis_prompt(self, campaign_name: str, analysis: Dict[str, Any]) -> List[Dict[str, str]]:
        """Build comprehensive prompt for LLM campaign analysis."""
        
        # Format agent breakdown
        agent_summary = ""
        if analysis.get('agent_metrics'):
            agent_summary = "\n\nAGENT PERFORMANCE DATA:\n"
            for agent in analysis['agent_metrics']:
                agent_summary += f"""
Agent: {agent['name']}
- Total Calls: {agent['total_calls']}
- Late Hello Bad: {agent['late_hello_bad']}
- Releasing Bad: {agent['releasing_bad']}
- Rebuttal Skipped: {agent['rebuttal_bad']}
- Avg Intro Score: {agent['avg_intro_score']}%
- Common Status: {agent['common_status']}
- Performance Score: {agent['performance_score']}%
"""
        
        kpis = analysis.get('kpis', {})
        
        user_prompt = f"""Based on this campaign data, generate a professional performance report in markdown format.

CAMPAIGN: {campaign_name}
TOTAL CALLS: {analysis.get('total_calls', 0)}
AGENTS AUDITED: {analysis.get('unique_agents', 0)}

OVERALL KPI METRICS:
- Late Hello Detection: {kpis.get('late_hello', {}).get('good', 0)} good, {kpis.get('late_hello', {}).get('bad', 0)} bad ({kpis.get('late_hello', {}).get('pct_good', 0)}% good)
- Releasing Detection: {kpis.get('releasing', {}).get('good', 0)} good, {kpis.get('releasing', {}).get('bad', 0)} bad ({kpis.get('releasing', {}).get('pct_good', 0)}% good)
- Rebuttal Detection: {kpis.get('rebuttal', {}).get('good', 0)} good, {kpis.get('rebuttal', {}).get('bad', 0)} bad ({kpis.get('rebuttal', {}).get('pct_good', 0)}% good)
{agent_summary}

Generate a report with EXACTLY this structure:

### **Overall Campaign Summary**
- **Total Calls Audited:** [number]
- **Agents Audited:** [number]

---

### **Key Performance Indicators (KPIs)**

| Metric | Good (No Issue) | Bad (Issue Found) | % Good |
|--------|-----------------|-------------------|---------|
| **Late Hello Detection** | X | X | X% |
| **Releasing Detection** | X | X | X% |
| **Rebuttal Detection** | X | X | X% |

[Add 1-2 sentences analyzing the KPI results]

---

### **Agent-Level Performance Breakdown**

| Agent Name | Total Calls | Late Hello (Bad) | Releasing (Bad) | Rebuttal Skipped (Bad) | Avg. Intro Score | Status Trend |
|------------|-------------|-------------------|------------------|-------------------------|------------------|--------------|
[Fill in agent rows sorted by performance score, best to worst]

---

### **Rebuttal Analysis**
- **Calls with Rebuttals:** X/Y (Z%)
- **Calls without Rebuttals:** X/Y (Z%)
  - [List agents who skipped rebuttals with call counts]

[Add 1-2 sentences about rebuttal performance]

---

### **Lowest Performing Agents**
Based on **Intro Score** and **Rebuttal Skipping**:

1. **[Agent Name]**  
   - Intro Score: X% [if notably low]
   - Rebuttal Skipped: [Yes/No with details]
   - [Brief assessment]

[Repeat for bottom 2-3 agents if applicable]

---

### **Conclusion: Are Agents Doing Their Best?**
[2-3 sentence overall assessment using checkmarks ✅ and warnings ⚠️]

**Areas for Improvement:**  
- [Bullet point list of issues]

---

### **Recommendations**
1. [Specific actionable recommendation]
2. [Specific actionable recommendation]
3. [Specific actionable recommendation]

IMPORTANT:
- Use markdown tables EXACTLY as shown
- Include actual numbers from the data
- Be specific and data-driven
- Use ✅ and ⚠️ symbols for visual clarity
- Keep analysis professional and actionable
"""
        
        system_prompt = """You are a sales performance analyst specializing in campaign audits. 
Generate detailed, data-driven reports using markdown tables and specific metrics.
Focus on agent performance, rebuttal usage, and actionable coaching recommendations.
Always match the exact report structure requested."""
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    
    def generate_report(self, df: pd.DataFrame, campaign_name: str) -> str:
        """
        Generate AI-powered campaign performance report with detailed tables.
        
        Args:
            df: Campaign audit dataframe with call data
            campaign_name: Name of the campaign
        
        Returns:
            Markdown-formatted report string with tables
        """
        try:
            logger.info(f"Generating comprehensive AI report for campaign: {campaign_name}")
            
            # Analyze campaign data
            analysis = self._analyze_campaign_data(df)
            
            if not analysis:
                return "❌ **Error:** No data available to generate report."
            
            # Build prompt and call LLM
            messages = self._build_analysis_prompt(campaign_name, analysis)
            report = self._call_groq_api(messages, max_tokens=3000)
            
            # Add metadata header
            timestamp = datetime.now().strftime("%Y-%m-%d %I:%M %p")
            header = f"# 🤖 Campaign Performance Report\n\n"
            header += f"**Campaign:** {campaign_name}  \n"
            header += f"**Generated:** {timestamp}  \n"
            header += f"**Powered by:** Groq AI (llama-3.1-8b-instant)  \n\n"
            header += "---\n\n"
            
            full_report = header + report
            
            logger.info(f"Successfully generated detailed report for {campaign_name}")
            return full_report
            
        except Exception as e:
            logger.error(f"Failed to generate campaign report: {e}", exc_info=True)
            return f"❌ **Error generating report:** {str(e)}\n\nPlease check your Groq API key and internet connection."


# Singleton instance for easy import
_report_generator = None

def get_report_generator() -> CampaignReportGenerator:
    """Get singleton campaign report generator instance."""
    global _report_generator
    if _report_generator is None:
        _report_generator = CampaignReportGenerator()
    return _report_generator
