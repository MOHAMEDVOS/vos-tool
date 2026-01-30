"""
LLM-Powered Campaign Performance Report Generator
Uses Groq (llama-3.1-8b-instant) with strict data accuracy.
Clean template matching user's exact format.
"""

import os
import re
import logging
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)


class CampaignReportGenerator:
    """Generates accurate AI-powered campaign performance reports."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.1-8b-instant"):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is required")
        
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        logger.info(f"CampaignReportGenerator initialized with model: {model}")
    
    def _call_groq_api(self, messages: List[Dict[str, str]], max_tokens: int = 3000) -> str:
        """Call Groq API with low temperature for accuracy."""
        import requests
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }
        
        try:
            response = requests.post(self.base_url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"Groq API call failed: {e}")
            raise
    
    def _calculate_stats(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate all statistics from actual data."""
        total_calls = len(df)
        unique_agents = df['Agent Name'].nunique() if 'Agent Name' in df.columns else 0
        
        # KPIs
        late_hello_bad = len(df[df['Late Hello Detection'] == 'Yes']) if 'Late Hello Detection' in df.columns else 0
        releasing_bad = len(df[df['Releasing Detection'] == 'Yes']) if 'Releasing Detection' in df.columns else 0
        rebuttal_no = len(df[df['Rebuttal Detection'] == 'No']) if 'Rebuttal Detection' in df.columns else 0
        rebuttal_yes = total_calls - rebuttal_no
        
        return {
            'total_calls': total_calls,
            'unique_agents': unique_agents,
            'late_hello': {
                'good': total_calls - late_hello_bad,
                'bad': late_hello_bad,
                'pct': round((total_calls - late_hello_bad) / total_calls * 100) if total_calls > 0 else 0
            },
            'releasing': {
                'good': total_calls - releasing_bad,
                'bad': releasing_bad,
                'pct': round((total_calls - releasing_bad) / total_calls * 100) if total_calls > 0 else 0
            },
            'rebuttal': {
                'good': rebuttal_yes,
                'bad': rebuttal_no,
                'pct': round(rebuttal_yes / total_calls * 100) if total_calls > 0 else 0
            }
        }
    
    def _get_agent_data(self, df: pd.DataFrame) -> List[Dict]:
        """Get per-agent performance data."""
        agent_data = []
        
        if 'Agent Name' not in df.columns:
            return agent_data
        
        for agent in df['Agent Name'].unique():
            agent_df = df[df['Agent Name'] == agent]
            calls = len(agent_df)
            
            late_hello_bad = len(agent_df[agent_df['Late Hello Detection'] == 'Yes']) if 'Late Hello Detection' in df.columns else 0
            releasing_bad = len(agent_df[agent_df['Releasing Detection'] == 'Yes']) if 'Releasing Detection' in df.columns else 0
            rebuttal_bad = len(agent_df[agent_df['Rebuttal Detection'] == 'No']) if 'Rebuttal Detection' in df.columns else 0
            
            # Calculate avg intro score
            avg_intro = 0
            if 'Intro Score' in df.columns:
                try:
                    scores = agent_df['Intro Score'].astype(str).str.replace('%', '').astype(float)
                    avg_intro = round(scores.mean(), 2)
                except:
                    avg_intro = 0
            
            # Get status
            status = 'N/A'
            if 'Status' in df.columns:
                try:
                    status = agent_df['Status'].mode()[0]
                except:
                    status = 'N/A'
            
            agent_data.append({
                'name': agent,
                'calls': calls,
                'late_hello_bad': late_hello_bad,
                'releasing_bad': releasing_bad,
                'rebuttal_bad': rebuttal_bad,
                'avg_intro': avg_intro,
                'status': status
            })
        
        # Sort by intro score descending
        agent_data.sort(key=lambda x: x['avg_intro'], reverse=True)
        return agent_data
    
    def _get_rebuttal_skippers(self, df: pd.DataFrame) -> List[Dict]:
        """Get agents who skipped rebuttals."""
        skippers = []
        
        if 'Agent Name' not in df.columns or 'Rebuttal Detection' not in df.columns:
            return skippers
        
        for agent in df['Agent Name'].unique():
            agent_df = df[df['Agent Name'] == agent]
            skipped = len(agent_df[agent_df['Rebuttal Detection'] == 'No'])
            if skipped > 0:
                skippers.append({'name': agent, 'skipped': skipped})
        
        return skippers
    
    def _get_lowest_performers(self, agent_data: List[Dict]) -> List[Dict]:
        """Get lowest performing agents based on intro score and issues."""
        # Sort by intro score ascending (lowest first), then by issues
        sorted_agents = sorted(agent_data, key=lambda x: (x['avg_intro'], -x['rebuttal_bad']))
        return sorted_agents[:3]  # Return bottom 3
    
    def _build_prompt(self, campaign_name: str, stats: Dict, agent_data: List[Dict], 
                      skippers: List[Dict], lowest: List[Dict]) -> List[Dict[str, str]]:
        """Build the prompt with pre-calculated data."""
        
        # Build agent table
        agent_table = "| Agent Name | Total Calls | Late Hello (Bad) | Releasing (Bad) | Rebuttal Skipped (Bad) | Avg. Intro Score | Status Trend |\n"
        agent_table += "|------------|-------------|-------------------|------------------|-------------------------|------------------|--------------||\n"
        for a in agent_data:
            agent_table += f"| **{a['name']}** | {a['calls']} | {a['late_hello_bad']} | {a['releasing_bad']} | {a['rebuttal_bad']} | {a['avg_intro']}% | {a['status']} |\n"
        
        # Build skippers list
        skipper_text = ""
        if skippers:
            skipper_names = ", ".join([f"{s['name']} ({s['skipped']} call{'s' if s['skipped'] > 1 else ''})" for s in skippers])
            skipper_text = f"  - {skipper_names}"
        
        # Build lowest performers section
        lowest_text = ""
        for i, agent in enumerate(lowest, 1):
            lowest_text += f"""
{i}. **{agent['name']}**  
   - Intro Score: {agent['avg_intro']}%{' (lowest in dataset)' if i == 1 and agent['avg_intro'] < 80 else ''}
   - Rebuttal Skipped: {'Yes' if agent['rebuttal_bad'] > 0 else 'No'}
   - {agent['calls']} call{'s' if agent['calls'] > 1 else ''} audited.
"""
        
        user_prompt = f"""
Generate a Campaign Performance Report using EXACTLY this template and data.

## DATA (USE THESE EXACT NUMBERS):

Campaign: {campaign_name}
Total Calls: {stats['total_calls']}
Agents: {stats['unique_agents']}

KPIs:
- Late Hello: Good={stats['late_hello']['good']}, Bad={stats['late_hello']['bad']}, %Good={stats['late_hello']['pct']}%
- Releasing: Good={stats['releasing']['good']}, Bad={stats['releasing']['bad']}, %Good={stats['releasing']['pct']}%
- Rebuttal: Good={stats['rebuttal']['good']}, Bad={stats['rebuttal']['bad']}, %Good={stats['rebuttal']['pct']}%

Agent Data:
{agent_table}

Rebuttal Skippers: {skipper_text if skipper_text else "None"}

---

## GENERATE REPORT IN THIS EXACT FORMAT:

### **Overall Campaign Summary**
- **Total Calls Audited:** {stats['total_calls']}
- **Agents Audited:** {stats['unique_agents']}

---

### **Key Performance Indicators (KPIs)**

| Metric | Good (No Issue) | Bad (Issue Found) | % Good |
|--------|-----------------|-------------------|---------|
| **Late Hello Detection** | {stats['late_hello']['good']} | {stats['late_hello']['bad']} | {stats['late_hello']['pct']}% |
| **Releasing Detection** | {stats['releasing']['good']} | {stats['releasing']['bad']} | {stats['releasing']['pct']}% |
| **Rebuttal Detection** | {stats['rebuttal']['good']} | {stats['rebuttal']['bad']} | {stats['rebuttal']['pct']}% |

[Add 2 lines: ✅ for what's good, ⚠️ for issues - based on the data above]

---

### **Agent-Level Performance Breakdown**

{agent_table}

---

### **Rebuttal Analysis**
- **Calls with Rebuttals:** {stats['rebuttal']['good']}/{stats['total_calls']} ({stats['rebuttal']['pct']}%)
- **Calls without Rebuttals:** {stats['rebuttal']['bad']}/{stats['total_calls']} ({100 - stats['rebuttal']['pct']}%)
{skipper_text}

[Add 1-2 sentences about rebuttal performance based on the numbers]

---

### **Lowest Performing Agents**
Based on **Intro Score** and **Rebuttal Skipping**:

{lowest_text}

---

### **Conclusion: Are Agents Doing Their Best?**
[Write 2-3 sentences using ✅ for positives and ⚠️ for issues, based ONLY on the data above]

**Areas for Improvement:**  
- [List 1-3 bullet points based on actual issues found]

---

### **Recommendations**
1. [First recommendation based on data]
2. [Second recommendation based on data]
3. [Third recommendation based on data]

---

IMPORTANT: Use ONLY the numbers provided above. Do not calculate new metrics.
"""
        
        system_prompt = """You are a call center performance analyst. 
Generate a clean, professional report using ONLY the data provided.
Use the exact format and structure requested.
Do not add new metrics or calculations - use only what's given.
Keep analysis focused on the actual numbers provided."""
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    
    def generate_report(self, df: pd.DataFrame, campaign_name: str) -> str:
        """Generate campaign performance report."""
        try:
            logger.info(f"Generating report for campaign: {campaign_name}")
            
            if df.empty:
                return "❌ **Error:** No data available to generate report."
            
            # Calculate all stats
            stats = self._calculate_stats(df)
            agent_data = self._get_agent_data(df)
            skippers = self._get_rebuttal_skippers(df)
            lowest = self._get_lowest_performers(agent_data)
            
            # Build prompt and call LLM
            messages = self._build_prompt(campaign_name, stats, agent_data, skippers, lowest)
            report = self._call_groq_api(messages)
            
            # Add header
            timestamp = datetime.now().strftime("%Y-%m-%d %I:%M %p")
            header = f"# 🤖 Campaign Performance Report\n\n"
            header += f"**Campaign:** {campaign_name}  \n"
            header += f"**Generated:** {timestamp}  \n"
            header += f"**Powered by:** Groq AI  \n\n"
            header += "---\n\n"
            
            return header + report
            
        except Exception as e:
            logger.error(f"Failed to generate report: {e}", exc_info=True)
            return f"❌ **Error generating report:** {str(e)}"


# Singleton instance
_report_generator = None

def get_report_generator() -> CampaignReportGenerator:
    """Get singleton campaign report generator instance."""
    global _report_generator
    if _report_generator is None:
        _report_generator = CampaignReportGenerator()
    return _report_generator
