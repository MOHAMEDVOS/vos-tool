"""
LLM-Powered Campaign Performance Report Generator (ACCURACY-FOCUSED)
Uses Groq (llama-3.1-8b-instant) with strict data validation to prevent hallucinations.
All statistics are pre-calculated from actual data before LLM receives them.
"""

import os
import re
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from collections import Counter
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)


class CampaignReportGenerator:
    """Generates accurate AI-powered campaign performance reports with data validation."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.1-8b-instant"):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is required")
        
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        logger.info(f"CampaignReportGenerator initialized with model: {model}")
    
    def _call_groq_api(self, messages: List[Dict[str, str]], max_tokens: int = 4000) -> str:
        """Call Groq API with strict temperature settings."""
        import requests
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.05,
            "max_tokens": max_tokens,
            "top_p": 0.9,
        }
        
        try:
            response = requests.post(self.base_url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"Groq API call failed: {e}")
            raise
    
    def _calculate_real_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate ALL statistics from actual data."""
        total_calls = len(df)
        unique_agents = df['Agent Name'].nunique() if 'Agent Name' in df.columns else 0
        
        stats = {
            'total_calls': total_calls,
            'unique_agents': unique_agents,
        }
        
        # KPIs
        if 'Late Hello Detection' in df.columns:
            bad = len(df[df['Late Hello Detection'] == 'Yes'])
            stats['late_hello'] = {'good': total_calls - bad, 'bad': bad,
                'pct_good': round((total_calls - bad) / total_calls * 100, 1) if total_calls > 0 else 0}
        else:
            stats['late_hello'] = {'good': total_calls, 'bad': 0, 'pct_good': 100.0}
        
        if 'Releasing Detection' in df.columns:
            bad = len(df[df['Releasing Detection'] == 'Yes'])
            stats['releasing'] = {'good': total_calls - bad, 'bad': bad,
                'pct_good': round((total_calls - bad) / total_calls * 100, 1) if total_calls > 0 else 0}
        else:
            stats['releasing'] = {'good': total_calls, 'bad': 0, 'pct_good': 100.0}
        
        if 'Rebuttal Detection' in df.columns:
            yes = len(df[df['Rebuttal Detection'] == 'Yes'])
            no = len(df[df['Rebuttal Detection'] == 'No'])
            stats['rebuttal'] = {'yes': yes, 'no': no,
                'pct_yes': round(yes / total_calls * 100, 1) if total_calls > 0 else 0}
        else:
            stats['rebuttal'] = {'yes': total_calls, 'no': 0, 'pct_yes': 100.0}
        
        return stats
    
    def _extract_real_transcript_issues(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Scan actual transcripts for issues."""
        issues = {
            'comprehension_count': 0,
            'comprehension_agents': {},
            'comprehension_examples': [],
            'script_error_count': 0,
            'script_error_agents': {},
            'script_error_examples': [],
        }
        
        if 'Transcription' not in df.columns:
            return issues
        
        comprehension_patterns = [r"can'?t understand", r"don'?t understand", r"pardon\??"]
        script_errors = [('interestted', 'interested'), ('sellling', 'selling')]
        
        for idx, row in df.iterrows():
            agent = row.get('Agent Name', 'Unknown')
            transcript = str(row.get('Transcription', '')).lower()
            
            if not transcript or transcript == 'nan':
                continue
            
            for pattern in comprehension_patterns:
                if re.search(pattern, transcript):
                    issues['comprehension_count'] += 1
                    issues['comprehension_agents'][agent] = issues['comprehension_agents'].get(agent, 0) + 1
                    break
            
            for error, correction in script_errors:
                if error in transcript:
                    issues['script_error_count'] += 1
                    if agent not in issues['script_error_agents']:
                        issues['script_error_agents'][agent] = []
                    issues['script_error_agents'][agent].append(error)
        
        return issues
    
    def _calculate_agent_performance(self, df: pd.DataFrame, issues: Dict) -> List[Dict]:
        """Calculate per-agent performance from ACTUAL data."""
        agent_data = []
        
        if 'Agent Name' not in df.columns:
            return agent_data
        
        for agent in df['Agent Name'].unique():
            agent_df = df[df['Agent Name'] == agent]
            agent_calls = len(agent_df)
            
            data = {
                'name': agent,
                'calls': agent_calls,
                'late_hello_bad': len(agent_df[agent_df.get('Late Hello Detection', pd.Series()) == 'Yes']) if 'Late Hello Detection' in df.columns else 0,
                'releasing_bad': len(agent_df[agent_df.get('Releasing Detection', pd.Series()) == 'Yes']) if 'Releasing Detection' in df.columns else 0,
                'rebuttal_no': len(agent_df[agent_df.get('Rebuttal Detection', pd.Series()) == 'No']) if 'Rebuttal Detection' in df.columns else 0,
                'avg_intro_score': 0,
                'common_status': 'N/A',
                'comprehension_issues': issues['comprehension_agents'].get(agent, 0),
                'script_errors': len(issues['script_error_agents'].get(agent, []))
            }
            
            if 'Intro Score' in df.columns:
                try:
                    scores = agent_df['Intro Score'].astype(str).str.replace('%', '').astype(float)
                    data['avg_intro_score'] = round(scores.mean(), 1)
                except:
                    pass
            
            if 'Status' in df.columns:
                try:
                    data['common_status'] = agent_df['Status'].mode()[0]
                except:
                    pass
            
            total_issues = data['late_hello_bad'] + data['releasing_bad'] + data['rebuttal_no'] + data['comprehension_issues']
            data['tier'] = '🟢' if total_issues == 0 else ('🟡' if total_issues <= 2 else '🔴')
            
            agent_data.append(data)
        
        agent_data.sort(key=lambda x: x['late_hello_bad'] + x['releasing_bad'] + x['rebuttal_no'])
        return agent_data
    
    def _build_accurate_prompt(self, campaign_name: str, stats: Dict, 
                                issues: Dict, agent_data: List[Dict]) -> List[Dict[str, str]]:
        """Build prompt with PRE-CALCULATED statistics."""
        
        agent_table = "| Agent | Calls | Late Hello | Releasing | Rebuttal Skip | Intro | Status | Tier |\n"
        agent_table += "|-------|-------|------------|-----------|---------------|-------|--------|------|\n"
        for a in agent_data:
            agent_table += f"| {a['name'][:20]} | {a['calls']} | {a['late_hello_bad']} | {a['releasing_bad']} | {a['rebuttal_no']} | {a['avg_intro_score']}% | {a['common_status']} | {a['tier']} |\n"
        
        rebuttal_skippers = [a for a in agent_data if a['rebuttal_no'] > 0]
        skipper_text = "\n".join([f"- {a['name']}: {a['rebuttal_no']}x" for a in rebuttal_skippers]) if rebuttal_skippers else "None"
        
        tier1, tier2, tier3 = [a for a in agent_data if a['tier']=='🟢'], [a for a in agent_data if a['tier']=='🟡'], [a for a in agent_data if a['tier']=='🔴']
        
        user_prompt = f"""
# CAMPAIGN REPORT - USE THESE EXACT NUMBERS

**Campaign:** {campaign_name}
**Total Calls:** {stats['total_calls']} | **Agents:** {stats['unique_agents']}

## KPIs (USE EXACTLY):
| Metric | Good | Bad | % Good |
|--------|------|-----|--------|
| Late Hello | {stats['late_hello']['good']} | {stats['late_hello']['bad']} | {stats['late_hello']['pct_good']}% |
| Releasing | {stats['releasing']['good']} | {stats['releasing']['bad']} | {stats['releasing']['pct_good']}% |
| Rebuttal | {stats['rebuttal']['yes']} | {stats['rebuttal']['no']} | {stats['rebuttal']['pct_yes']}% |

## Rebuttal Stats:
- With Rebuttals: {stats['rebuttal']['yes']}/{stats['total_calls']} ({stats['rebuttal']['pct_yes']}%)
- Skipped: {stats['rebuttal']['no']}
- Agents who skipped: {skipper_text}

## Transcript Issues:
- Comprehension: {issues['comprehension_count']} incidents
- Script errors: {issues['script_error_count']} incidents

## Agent Table:
{agent_table}

## Tiers: 🟢 {len(tier1)} | 🟡 {len(tier2)} | 🔴 {len(tier3)}

Generate a CONCISE report with:
1. KPI summary (use table above)
2. Top issues (2-3 bullets)
3. Agent tiers (list names per tier)
4. 3 action items

Keep it SHORT - no more than 20 lines. Use ✅ ⚠️ symbols.
"""
        
        system_prompt = "You format pre-calculated campaign data into concise reports. Use ONLY the numbers provided. Keep output under 20 lines."
        
        return [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    
    def generate_report(self, df: pd.DataFrame, campaign_name: str) -> str:
        """Generate accurate AI-powered campaign performance report."""
        try:
            if df.empty:
                return "❌ No data available."
            
            stats = self._calculate_real_statistics(df)
            issues = self._extract_real_transcript_issues(df)
            agent_data = self._calculate_agent_performance(df, issues)
            messages = self._build_accurate_prompt(campaign_name, stats, issues, agent_data)
            report = self._call_groq_api(messages, max_tokens=2000)
            
            timestamp = datetime.now().strftime("%Y-%m-%d %I:%M %p")
            header = f"**Campaign:** {campaign_name} | **Generated:** {timestamp}\n\n---\n\n"
            
            return header + report
            
        except Exception as e:
            logger.error(f"Failed to generate report: {e}", exc_info=True)
            return f"❌ Error: {str(e)}"


_report_generator = None

def get_report_generator() -> CampaignReportGenerator:
    global _report_generator
    if _report_generator is None:
        _report_generator = CampaignReportGenerator()
    return _report_generator
