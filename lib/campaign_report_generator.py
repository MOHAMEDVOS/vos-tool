"""
LLM-Powered Campaign Performance Report Generator (STRICT DATA-DRIVEN - SIMPLIFIED + NEW METRICS)
Uses Groq (llama-3.1-8b-instant) strictly for formatting.
ALL analysis, examples, and recommendations are pre-calculated in Python to prevent hallucination.
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
    """Generates strictly accurate AI-powered campaign performance reports."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.1-8b-instant"):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is required")
        
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        logger.info(f"CampaignReportGenerator initialized with model: {model}")
    
    def _call_groq_api(self, messages: List[Dict[str, str]], max_tokens: int = 4000) -> str:
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
    
    def _find_column(self, df: pd.DataFrame, keywords: List[str]) -> Optional[str]:
        """Case-insensitive fuzzy match for column names."""
        for col in df.columns:
            col_lower = col.lower()
            for kw in keywords:
                if kw.lower() in col_lower:
                    return col
        return None

    def _calculate_real_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        total_calls = len(df)
        unique_agents = df['Agent Name'].nunique() if 'Agent Name' in df.columns else 0
        
        stats = {
            'total_calls': total_calls,
            'unique_agents': unique_agents,
        }
        
        # KEY METRICS: Count total Good (Yes) / Bad (No/Missing)
        
        # 1. Agent Intro
        col_intro = self._find_column(df, ['Agent Intro', 'Intro Detected'])
        if col_intro:
            intro_good = len(df[df[col_intro] == 'Yes'])
            stats['agent_intro'] = {
                'good': intro_good,
                'pct_good': round(intro_good / total_calls * 100, 1) if total_calls > 0 else 0
            }
        else:
            stats['agent_intro'] = {'good': 0, 'pct_good': 0, 'missing_column': True}

        # 2. Reason for calling
        col_reason = self._find_column(df, ['Reason for calling', 'Reason For Calling', 'Calling Reason'])
        if col_reason:
            reason_good = len(df[df[col_reason] == 'Yes'])
            stats['reason_for_calling'] = {
                'good': reason_good,
                'pct_good': round(reason_good / total_calls * 100, 1) if total_calls > 0 else 0
            }
        else:
            stats['reason_for_calling'] = {'good': 0, 'pct_good': 0, 'missing_column': True}
            
        # 3. Owner Name
        col_owner = self._find_column(df, ['Owner Name', 'Owner Verified'])
        if col_owner:
            owner_good = len(df[df[col_owner] == 'Yes'])
            stats['owner_name'] = {
                'good': owner_good,
                'pct_good': round(owner_good / total_calls * 100, 1) if total_calls > 0 else 0
            }
        else:
            stats['owner_name'] = {'good': 0, 'pct_good': 0, 'missing_column': True}

        # 4. Late Hello (Yes is Bad)
        if 'Late Hello Detection' in df.columns:
            late_hello_bad = len(df[df['Late Hello Detection'] == 'Yes'])
            stats['late_hello'] = {
                'good': total_calls - late_hello_bad,
                'pct_good': round((total_calls - late_hello_bad) / total_calls * 100, 1) if total_calls > 0 else 0
            }
        else:
            stats['late_hello'] = {'good': total_calls, 'pct_good': 100.0}
        
        # 5. Releasing (Yes is Bad)
        if 'Releasing Detection' in df.columns:
            releasing_bad = len(df[df['Releasing Detection'] == 'Yes'])
            stats['releasing'] = {
                'good': total_calls - releasing_bad,
                'pct_good': round((total_calls - releasing_bad) / total_calls * 100, 1) if total_calls > 0 else 0
            }
        else:
            stats['releasing'] = {'good': total_calls, 'pct_good': 100.0}
        
        # 6. Rebuttals (Yes is Good)
        if 'Rebuttal Detection' in df.columns:
            rebuttal_yes = len(df[df['Rebuttal Detection'] == 'Yes'])
            rebuttal_no = len(df[df['Rebuttal Detection'] == 'No'])
            stats['rebuttal'] = {
                'yes': rebuttal_yes,
                'no': rebuttal_no,
                'pct_yes': round(rebuttal_yes / total_calls * 100, 1) if total_calls > 0 else 0
            }
        else:
            stats['rebuttal'] = {'yes': total_calls, 'no': 0, 'pct_yes': 100.0}
            
        return stats

    def _calculate_agent_performance(self, df: pd.DataFrame, stats: Dict) -> List[Dict]:
        agent_data = []
        if 'Agent Name' not in df.columns: return []
        
        col_intro = self._find_column(df, ['Agent Intro', 'Intro Detected'])
        col_reason = self._find_column(df, ['Reason for calling', 'Reason For Calling', 'Calling Reason'])
        col_owner = self._find_column(df, ['Owner Name', 'Owner Verified'])

        for agent in df['Agent Name'].unique():
            agent_df = df[df['Agent Name'] == agent]
            calls = len(agent_df)
            
            # Count Issues
            late_bad = len(agent_df[agent_df['Late Hello Detection'] == 'Yes']) if 'Late Hello Detection' in df.columns else 0
            release_bad = len(agent_df[agent_df['Releasing Detection'] == 'Yes']) if 'Releasing Detection' in df.columns else 0
            rebuttal_skip = len(agent_df[agent_df['Rebuttal Detection'] == 'No']) if 'Rebuttal Detection' in df.columns else 0
            
            # New Metrics Issues
            intro_bad = len(agent_df[agent_df[col_intro] != 'Yes']) if col_intro else 0
            reason_bad = len(agent_df[agent_df[col_reason] != 'Yes']) if col_reason else 0
            owner_bad = len(agent_df[agent_df[col_owner] != 'Yes']) if col_owner else 0

            # Intro Score
            avg_intro = 0
            if 'Intro Score' in df.columns:
                try:
                    scores = agent_df['Intro Score'].astype(str).str.replace('%','').astype(float)
                    avg_intro = round(scores.mean(), 1)
                except: pass

            total_issues = late_bad + release_bad + rebuttal_skip + intro_bad + reason_bad + owner_bad
            
            # Simplified Tier Logic
            if total_issues == 0 and avg_intro >= 90: tier = '🟢'
            elif total_issues <= 1 and avg_intro >= 80: tier = '🟢'
            elif total_issues <= 3: tier = '🟡'
            else: tier = '🔴'
            
            agent_data.append({
                'name': agent,
                'calls': calls,
                'avg_intro_score': avg_intro,
                'late_hello_bad': late_bad,
                'releasing_bad': release_bad,
                'rebuttal_no': rebuttal_skip,
                'intro_bad': intro_bad,
                'reason_bad': reason_bad,
                'owner_bad': owner_bad,
                'tier': tier
            })
            
        return sorted(agent_data, key=lambda x: x['avg_intro_score'], reverse=True)

    def _generate_analysis_sections(self, stats: Dict, agents: List[Dict]) -> Dict[str, str]:
        """Python-side generation of simplified analytic text."""
        
        # 1. Overall Status
        tier1_count = len([a for a in agents if a['tier'] == '🟢'])
        tier3_count = len([a for a in agents if a['tier'] == '🔴'])
        if tier3_count == 0 and tier1_count >= len(agents)/2:
            status = "🟢 Excellent - High Performance"
        elif tier3_count > len(agents)/3:
            status = "🔴 Needs Attention - Multiple Critical Issues"
        else:
            status = "🟡 Good - Standard Performance"
            
        # 2. Strengths & Weaknesses
        strengths = []
        weaknesses = []
        
        # Logic: If metric exists and >= 80%, consider strength. If < 80%, weakness.
        
        # Late Hello
        if stats['late_hello']['pct_good'] >= 80: strengths.append(f"Prompt Responses ({stats['late_hello']['pct_good']}%)")
        else: weaknesses.append(f"Late Hello Issues ({100-stats['late_hello']['pct_good']:.1f}%)")
        
        # Releasing
        if stats['releasing']['pct_good'] >= 80: strengths.append(f"Professional Endings ({stats['releasing']['pct_good']}%)")
        else: weaknesses.append(f"Improper Releasing ({100-stats['releasing']['pct_good']:.1f}%)")
        
        # Rebuttal
        if stats['rebuttal']['pct_yes'] >= 80: strengths.append(f"Persistence ({stats['rebuttal']['pct_yes']}%)")
        else: weaknesses.append(f"Rebuttals Missed ({stats['rebuttal']['no']} incidents)")

        # Intro
        if not stats.get('agent_intro', {}).get('missing_column'):
            if stats['agent_intro']['pct_good'] >= 80: strengths.append(f"Good Intros ({stats['agent_intro']['pct_good']}%)")
            else: weaknesses.append(f"Missing Intros ({100-stats['agent_intro']['pct_good']:.1f}%)")
            
        # Reason
        if not stats.get('reason_for_calling', {}).get('missing_column'):
            if stats['reason_for_calling']['pct_good'] >= 80: strengths.append(f"Clear Reason ({stats['reason_for_calling']['pct_good']}%)")
            else: weaknesses.append(f"Unstated Reason ({100-stats['reason_for_calling']['pct_good']:.1f}%)")
            
        # Owner
        if not stats.get('owner_name', {}).get('missing_column'):
            if stats['owner_name']['pct_good'] >= 80: strengths.append(f"Owner Verified ({stats['owner_name']['pct_good']}%)")
            else: weaknesses.append(f"Unverified Owners ({100-stats['owner_name']['pct_good']:.1f}%)")
        
        if not strengths: strengths.append("Calls Completed")
        if not weaknesses: weaknesses.append("No Issues Found")
        
        # 3. Top Issues
        top_issues_text = ""
        problem_list = []
        
        # Check Rebuttals
        if stats['rebuttal']['no'] > 0:
            count = stats['rebuttal']['no']
            skippers = [a['name'] for a in agents if a['rebuttal_no'] > 0]
            if count > 0:
                problem_list.append((count, f"""
**1. MISSED REBUTTALS** ({count} incidents) 🟡
- **Problem:** Agents ending call too early after customer says 'No'.
- **Agents:** {', '.join(skippers[:3])}
"""))

        # Check Intro
        bad_intros = stats['total_calls'] - stats['agent_intro']['good'] if not stats.get('agent_intro', {}).get('missing_column') else 0
        if bad_intros > 0:
            count = bad_intros
            lazy_agents = [a['name'] for a in agents if a.get('intro_bad', 0) > 0]
            problem_list.append((count, f"""
**2. MISSING INTRO** ({count} incidents) 🟡
- **Problem:** Agents failing to introduce themselves properly.
- **Agents:** {', '.join(lazy_agents[:3])}
"""))

        # Check Reason for Calling
        col_reason = self._find_column(pd.DataFrame(agents), ['Reason for calling']) # Actually irrelevant here, used count above
        bad_reasons = stats['total_calls'] - stats['reason_for_calling']['good'] if not stats.get('reason_for_calling', {}).get('missing_column') else 0
        if bad_reasons > 0:
            count = bad_reasons
            vague_agents = [a['name'] for a in agents if a.get('reason_bad', 0) > 0]
            problem_list.append((count, f"""
**3. UNCLEAR REASON** ({count} incidents) 🟡
- **Problem:** Agents failing to state the reason for calling.
- **Agents:** {', '.join(vague_agents[:3])}
"""))

        # Check Owner Name
        bad_owners = stats['total_calls'] - stats['owner_name']['good'] if not stats.get('owner_name', {}).get('missing_column') else 0
        if bad_owners > 0:
            count = bad_owners
            lost_agents = [a['name'] for a in agents if a.get('owner_bad', 0) > 0]
            problem_list.append((count, f"""
**4. OWNER VERIFICATION FAILED** ({count} incidents) 🟡
- **Problem:** Agents failing to verify they are speaking to the correct owner.
- **Agents:** {', '.join(lost_agents[:3])}
"""))

        # Check Late Hello
        late_hello_bad = stats['total_calls'] - stats['late_hello']['good']
        if late_hello_bad > 0:
            count = late_hello_bad
            late_agents = [a['name'] for a in agents if a['late_hello_bad'] > 0]
            problem_list.append((count, f"""
**5. LATE HELLO** ({count} incidents) 🟡
- **Problem:** Delay in greeting the customer.
- **Agents:** {', '.join(late_agents[:3])}
"""))
            
        # Sort by count and join
        problem_list.sort(key=lambda x: x[0], reverse=True)
        top_issues_text = "\n".join([p[1] for p in problem_list[:3]])
        if not top_issues_text:
            top_issues_text = "Analysis complete. No major issues detected based on call metadata."

        # 4. Action Plan
        action_plan_text = ""
        if 'Intros' in str(weaknesses):
            action_plan_text += "**Priority:** Drill proper introduction script (Name + Company)\n"
        if 'Reason' in str(weaknesses):
            action_plan_text += "**Priority:** Practice stating reason for call clearly\n"
        if 'Owner' in str(weaknesses):
            action_plan_text += "**Priority:** Ensure agents ask for property owner explicitly\n"
        if 'Rebuttals' in str(weaknesses):
            action_plan_text += "**Priority:** Coach team on Objection Handling (Don't give up on first 'No')\n"
        
        if not action_plan_text:
            action_plan_text = "**Status:** Maintain current high performance standards."

        return {
            'status': status,
            'strengths': strengths[:3],
            'weaknesses': weaknesses[:3],
            'top_issues': top_issues_text,
            'action_plan': action_plan_text
        }

    def generate_report(self, df: pd.DataFrame, campaign_name: str) -> str:
        if df.empty: return "❌ No data available."
        
        # 1. Calculate simplified stats in Python
        stats = self._calculate_real_statistics(df)
        agents = self._calculate_agent_performance(df, stats)
        analysis = self._generate_analysis_sections(stats, agents)
        
        # 2. Build Tables
        tier1 = [a for a in agents if a['tier'] == '🟢' and a['calls'] >= 10]
        tier2 = [a for a in agents if a['tier'] == '🟡' and a['calls'] >= 10]
        tier3 = [a for a in agents if a['tier'] == '🔴']
        
        tier1_table = ""
        if tier1:
            tier1_table = "| Agent | Calls | Score |\n|---|---|---|\n" + "\n".join([f"| {a['name']} | {a['calls']} | {a['avg_intro_score']}% |" for a in tier1[:5]])
        else:
            tier1_table = "No agents meet the minimum volume threshold (10 calls) for top performer status."
        
        tier2_table = ""
        if tier2:
             tier2_table = "| Agent | Calls | Issue |\n|---|---|---|\n" + "\n".join([f"| {a['name']} | {a['calls']} | {self._get_agent_issue(a)} |" for a in tier2[:5]])
        else:
             tier2_table = "No agents meet the criteria for coaching (min 10 calls)."

        tier3_table = ""
        if tier3:
             tier3_table = "| Agent | Calls | Critical Issue |\n|---|---|---|\n" + "\n".join([f"| {a['name']} | {a['calls']} | {self._get_agent_issue(a)} |" for a in tier3[:5]])

        # 3. Construct Prompt (With New Metrics)
        avg_score = sum(a['avg_intro_score'] for a in agents)/len(agents) if agents else 0
        
        # Dynamic Metric Rows (3x2 Layout)
        # Row 1: Responsiveness | Persistence
        row1 = f"| Late Hello | {stats['late_hello']['pct_good']}% | {self._status(stats['late_hello']['pct_good'])} | Rebuttal Usage | {stats['rebuttal']['pct_yes']}% | {self._status(stats['rebuttal']['pct_yes'])} |"
        
        # Row 2: Identity | Clarity
        intro_val = "N/A"
        intro_stat = "N/A"
        reason_val = "N/A"
        reason_stat = "N/A"
        
        if not stats.get('agent_intro', {}).get('missing_column'):
             intro_val = f"{stats['agent_intro']['pct_good']}%"
             intro_stat = self._status(stats['agent_intro']['pct_good'])
        
        if not stats.get('reason_for_calling', {}).get('missing_column'):
             reason_val = f"{stats['reason_for_calling']['pct_good']}%"
             reason_stat = self._status(stats['reason_for_calling']['pct_good'])
             
        row2 = f"| Agent Intro | {intro_val} | {intro_stat} | Calling Reason | {reason_val} | {reason_stat} |"
        
        # Row 3: Professionalism | Verification
        owner_val = "N/A"
        owner_stat = "N/A"
        if not stats.get('owner_name', {}).get('missing_column'):
             owner_val = f"{stats['owner_name']['pct_good']}%"
             owner_stat = self._status(stats['owner_name']['pct_good'])
             
        row3 = f"| Releasing | {stats['releasing']['pct_good']}% | {self._status(stats['releasing']['pct_good'])} | Owner Verify | {owner_val} | {owner_stat} |"
        
        metric_rows = f"{row1}\n{row2}\n{row3}\n"

        user_prompt = f"""
# GENERATE REPORT USING EXACTLY THIS CONTENT (NO CHANGES):

# {campaign_name} Campaign Dashboard
**Generated:** [Current Date] | **Calls:** {stats['total_calls']} | **Agents:** {stats['unique_agents']} | **Result:** {avg_score:.0f}%

## Quick Summary
**Status:** {analysis['status']}

| Strengths | Focus Areas |
|-----------|-------------|
{self._format_list_as_table_rows(analysis['strengths'], analysis['weaknesses'])}

---

## Key Metrics
| Metric | Score | Status | Metric | Score | Status |
|--------|-------|--------|--------|-------|--------|
{metric_rows}

---

## Agent Performance

### Top Performers (Min 10 Calls)
{tier1_table if tier1_table else "None"}

### Needs Coaching (Min 10 Calls)
{tier2_table if tier2_table else "None"}

### Urgent Attention (Unfiltered)
{tier3_table if tier3_table else "None"}

---

## Top Issues
{analysis['top_issues']}

---

## Action Plan
{analysis['action_plan']}
"""

        system_prompt = "You are a report formatter. Your ONLY job is to take the provided text and output it EXACTLY as written, ensuring the Markdown formatting is clean. DO NOT change ANY numbers, text, or examples."
        
        return self._call_groq_api([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])

    def _get_agent_issue(self, agent: Dict) -> str:
        if agent.get('intro_bad', 0) > 0: return "Missing Intro"
        if agent.get('reason_bad', 0) > 0: return "Missing Reason"
        if agent.get('owner_bad', 0) > 0: return "Owner Not Verified"
        if agent['rebuttal_no'] > 0: return "Skipped Rebuttal"
        if agent['late_hello_bad'] > 0: return "Late Hello"
        if agent['releasing_bad'] > 0: return "Improper Release"
        return "Low Score"

    def _status(self, val: float) -> str:
        # >80% = ✅
        # 70-80% = ⚠️
        # <70% = 🚨
        if val >= 80: return "✅"
        elif val >= 70: return "⚠️"
        else: return "🚨"

    def _format_list_as_table_rows(self, strengths: List[str], weaknesses: List[str]) -> str:
        rows = ""
        for i in range(max(len(strengths), len(weaknesses))):
            s = strengths[i] if i < len(strengths) else ""
            w = weaknesses[i] if i < len(weaknesses) else ""
            rows += f"| • {s} | • {w} |\n"
        return rows

_report_generator = None
def get_report_generator() -> CampaignReportGenerator:
    global _report_generator
    if _report_generator is None:
        _report_generator = CampaignReportGenerator()
    return _report_generator
