"""
LLM-Powered Campaign Performance Report Generator (STRICT DATA-DRIVEN)
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

    def _calculate_real_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        total_calls = len(df)
        unique_agents = df['Agent Name'].nunique() if 'Agent Name' in df.columns else 0
        
        stats = {
            'total_calls': total_calls,
            'unique_agents': unique_agents,
        }
        
        # KPIs
        if 'Late Hello Detection' in df.columns:
            late_hello_bad = len(df[df['Late Hello Detection'] == 'Yes'])
            stats['late_hello'] = {
                'good': total_calls - late_hello_bad,
                'pct_good': round((total_calls - late_hello_bad) / total_calls * 100, 1) if total_calls > 0 else 0
            }
        else:
            stats['late_hello'] = {'good': total_calls, 'pct_good': 100.0}
        
        if 'Releasing Detection' in df.columns:
            releasing_bad = len(df[df['Releasing Detection'] == 'Yes'])
            stats['releasing'] = {
                'good': total_calls - releasing_bad,
                'pct_good': round((total_calls - releasing_bad) / total_calls * 100, 1) if total_calls > 0 else 0
            }
        else:
            stats['releasing'] = {'good': total_calls, 'pct_good': 100.0}
        
        if 'Rebuttal Detection' in df.columns:
            # Note: "No" means rebuttal was skipped (Bad), "Yes" means used (Good)
            # Some entries might be N/A if calls didn't reach rebuttal stage? 
            # Assuming 'No' is the issue we track.
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

    def _extract_real_transcript_issues(self, df: pd.DataFrame) -> Dict[str, Any]:
        issues = {
            'comprehension_count': 0,
            'comprehension_agents': Counter(),
            'comprehension_examples': [],
            'script_error_count': 0,
            'script_error_agents': Counter(),
            'script_error_examples': []
        }
        
        if 'Transcription' not in df.columns:
            return issues
            
        comprehension_patterns = [r"can'?t understand", r"pardon\??", r"say.*again", r"repeat that"]
        script_errors = [
            ('interestted', 'interested'),
            ('sellling', 'selling'),
            ('propertty', 'property'),
            ('callingg', 'calling'),
            ('gardening', 'calling about'), # Common hallucination/ASR error
        ]

        for idx, row in df.iterrows():
            agent = row.get('Agent Name', 'Unknown')
            transcript = str(row.get('Transcription', '')).lower()
            if not transcript or transcript == 'nan': continue
            
            # Comprehension
            for pat in comprehension_patterns:
                match = re.search(pat, transcript)
                if match:
                    issues['comprehension_count'] += 1
                    issues['comprehension_agents'][agent] += 1
                    if len(issues['comprehension_examples']) < 2:
                        start = max(0, match.start() - 20)
                        end = min(len(transcript), match.end() + 20)
                        issues['comprehension_examples'].append({
                            'agent': agent,
                            'quote': f"...{transcript[start:end]}..."
                        })
                    break # Count per call
                    
            # Script Errors
            for err, corr in script_errors:
                if err in transcript:
                    issues['script_error_count'] += 1
                    issues['script_error_agents'][agent] += 1
                    if len(issues['script_error_examples']) < 2:
                        issues['script_error_examples'].append({
                            'agent': agent,
                            'error': err, 
                            'correction': corr
                        })
                    break

        return issues

    def _calculate_agent_performance(self, df: pd.DataFrame, stats: Dict, issues: Dict) -> List[Dict]:
        agent_data = []
        if 'Agent Name' not in df.columns: return []
        
        for agent in df['Agent Name'].unique():
            agent_df = df[df['Agent Name'] == agent]
            calls = len(agent_df)
            
            # Metadata Issues
            late_bad = len(agent_df[agent_df['Late Hello Detection'] == 'Yes']) if 'Late Hello Detection' in df.columns else 0
            release_bad = len(agent_df[agent_df['Releasing Detection'] == 'Yes']) if 'Releasing Detection' in df.columns else 0
            rebuttal_skip = len(agent_df[agent_df['Rebuttal Detection'] == 'No']) if 'Rebuttal Detection' in df.columns else 0
            
            # Transcript Issues
            comp_issues = issues['comprehension_agents'][agent]
            script_errs = issues['script_error_agents'][agent]
            
            # Intro Score
            avg_intro = 0
            if 'Intro Score' in df.columns:
                try:
                    scores = agent_df['Intro Score'].astype(str).str.replace('%','').astype(float)
                    avg_intro = round(scores.mean(), 1)
                except: pass

            total_issues = late_bad + release_bad + rebuttal_skip + comp_issues + script_errs
            
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
                'comprehension_issues': comp_issues,
                'script_errors': script_errs,
                'tier': tier
            })
            
        return sorted(agent_data, key=lambda x: x['avg_intro_score'], reverse=True)

    def _generate_analysis_sections(self, stats: Dict, issues: Dict, agents: List[Dict]) -> Dict[str, str]:
        """Python-side generation of all analytic text to prevent LLM hallucinations."""
        
        # 1. Overall Status
        tier1_count = len([a for a in agents if a['tier'] == '🟢'])
        tier3_count = len([a for a in agents if a['tier'] == '🔴'])
        
        if tier3_count == 0 and tier1_count > len(agents)/2:
            status = "🟢 Excellent - Team is performing well"
        elif tier3_count > len(agents)/3:
            status = "🔴 Needs Attention - Multiple agents struggling"
        else:
            status = "🟡 Good with Room for Improvement"
            
        # 2. Strengths & Weaknesses
        strengths = []
        weaknesses = []
        
        if stats['late_hello']['pct_good'] >= 95: strengths.append(f"Prompt Answering ({stats['late_hello']['pct_good']}%)")
        else: weaknesses.append(f"Late Hellos ({100-stats['late_hello']['pct_good']:.1f}%)")
        
        if stats['releasing']['pct_good'] >= 95: strengths.append(f"Professional Endings ({stats['releasing']['pct_good']}%)")
        else: weaknesses.append(f"Improper Releasing ({100-stats['releasing']['pct_good']:.1f}%)")
        
        if stats['rebuttal']['pct_yes'] >= 90: strengths.append(f"Effective Rebuttals ({stats['rebuttal']['pct_yes']}%)")
        else: weaknesses.append(f"Skipped Rebuttals ({stats['rebuttal']['no']} incidents)")
        
        if issues['script_error_count'] == 0: strengths.append("Perfect Script Accuracy")
        else: weaknesses.append(f"Script Accuracy ({issues['script_error_count']} errors)")
        
        if not strengths: strengths.append("Data collection successful")
        if not weaknesses: weaknesses.append("No major issues detected")
        
        # 3. Top Issues
        top_issues_text = ""
        problem_list = []
        
        # Check Script Errors
        if issues['script_error_count'] > 0:
            example = issues['script_error_examples'][0]
            count = issues['script_error_count']
            problem_list.append((count, f"""
**1. SCRIPT ERRORS** ({count} incidents) 🔴
- **Problem:** Agents misspelling or mispronouncing keywords
- **Example:** "{example['error']}" (should be "{example['correction']}")
- **Fix:** Review script pronunciation guide
- **Who:** {', '.join([k for k,v in issues['script_error_agents'].items() if v>0][:3])}
"""))
            
        # Check Comprehension
        if issues['comprehension_count'] > 0:
            example = issues['comprehension_examples'][0]
            count = issues['comprehension_count']
            problem_list.append((count, f"""
**2. COMPREHENSION ISSUES** ({count} incidents) 🟡
- **Problem:** Customers expressing confusion
- **Example:** "{example['quote']}"
- **Fix:** Speak slower, check audio clarity
- **Who:** {', '.join([k for k,v in issues['comprehension_agents'].items() if v>0][:3])}
"""))

        # Check Rebuttals
        if stats['rebuttal']['no'] > 0:
            count = stats['rebuttal']['no']
            skippers = [a['name'] for a in agents if a['rebuttal_no'] > 0]
            problem_list.append((count, f"""
**3. MISSED REBUTTALS** ({count} incidents) 🟡
- **Problem:** Ending call without making a second attempt
- **Fix:** Requirement: 1 rebuttal per refusal
- **Who:** {', '.join(skippers[:3])}
"""))
            
        # Sort by count and join
        problem_list.sort(key=lambda x: x[0], reverse=True)
        top_issues_text = "\n".join([p[1] for p in problem_list[:3]])
        if not top_issues_text:
            top_issues_text = "No major issues identified. Team performance is high."

        # 4. Action Plan
        action_plan_text = ""
        if 'Script Accuracy' in str(weaknesses):
            action_plan_text += "**Priority 1:** Script pronunciation drill (Focus: 'Interested', 'Selling')\n"
        if 'Rebuttals' in str(weaknesses):
            action_plan_text += "**Priority 2:** Rebuttal role-play (Requirement: 1 attempt/call)\n"
        if 'Comprehension' in str(top_issues_text):
            action_plan_text += "**Priority 3:** Audio clarity check & pacing training\n"
        
        if not action_plan_text:
            action_plan_text = "**Priority 1:** Maintain current performance standards\n**Priority 2:** Advanced sales training"

        return {
            'status': status,
            'strengths': strengths[:3],
            'weaknesses': weaknesses[:3],
            'top_issues': top_issues_text,
            'action_plan': action_plan_text
        }

    def generate_report(self, df: pd.DataFrame, campaign_name: str) -> str:
        if df.empty: return "❌ No data available."
        
        # 1. Calculate everything in Python
        stats = self._calculate_real_statistics(df)
        issues = self._extract_real_transcript_issues(df)
        agents = self._calculate_agent_performance(df, stats, issues)
        analysis = self._generate_analysis_sections(stats, issues, agents)
        
        # 2. Build Tables
        tier1 = [a for a in agents if a['tier'] == '🟢']
        tier2 = [a for a in agents if a['tier'] == '🟡']
        tier3 = [a for a in agents if a['tier'] == '🔴']
        
        tier1_table = ""
        if tier1:
            tier1_table = "| Agent | Calls | Score |\n|---|---|---|\n" + "\n".join([f"| {a['name']} | {a['calls']} | {a['avg_intro_score']}% |" for a in tier1[:5]])
        
        tier2_table = ""
        if tier2:
             tier2_table = "| Agent | Calls | Issue |\n|---|---|---|\n" + "\n".join([f"| {a['name']} | {a['calls']} | {self._get_agent_issue(a)} |" for a in tier2[:5]])

        tier3_table = ""
        if tier3:
             tier3_table = "| Agent | Calls | Critical Issue |\n|---|---|---|\n" + "\n".join([f"| {a['name']} | {a['calls']} | {self._get_agent_issue(a)} |" for a in tier3[:5]])

        # 3. Construct Prompt (Just filling slots)
        avg_score = sum(a['avg_intro_score'] for a in agents)/len(agents) if agents else 0
        top_agent = agents[0] if agents else {'name': 'N/A', 'avg_intro_score': 0}
        
        user_prompt = f"""
# GENERATE REPORT USING EXACTLY THIS CONTENT (NO CHANGES):

# 🚀 {campaign_name} Campaign Dashboard
**Generated:** [Current Date] | **Calls:** {stats['total_calls']} | **Agents:** {stats['unique_agents']} | **Avg Score:** {avg_score:.0f}%

## 📊 Quick Summary
**Status:** {analysis['status']}

| ✅ Strengths | ⚠️ Focus Areas |
|--------------|----------------|
{self._format_list_as_table_rows(analysis['strengths'], analysis['weaknesses'])}

---

## 🎯 Key Metrics
| Metric | Score | Status | Metric | Score | Status |
|--------|-------|--------|--------|-------|--------|
| Late Hello | {stats['late_hello']['pct_good']}% | {self._status(stats['late_hello']['pct_good'])} | Rebuttal Usage | {stats['rebuttal']['pct_yes']}% | {self._status(stats['rebuttal']['pct_yes'])} |
| Releasing | {stats['releasing']['pct_good']}% | {self._status(stats['releasing']['pct_good'])} | Script Accuracy | {100 - (issues['script_error_count']*2)}% | {self._status(100 - issues['script_error_count']*2)} |

---

## 👥 Agent Performance

### 🟢 Top Performers ({len(tier1)})
{tier1_table if tier1_table else "None"}

### 🟡 Needs Coaching ({len(tier2)})
{tier2_table if tier2_table else "None"}

### 🔴 Urgent Attention ({len(tier3)})
{tier3_table if tier3_table else "None"}

---

## 🚨 Top Issues
{analysis['top_issues']}

---

## 🛠️ Action Plan
**This Week:**
{analysis['action_plan']}

**Success Targets:**
- 100% Script Accuracy
- 95% Rebuttal Rate
- 0 Comprehension Incidents

---

## 💡 Bottom Line
**Status:** {analysis['status']}. 
**Focus:** Fix {analysis['weaknesses'][0] if analysis['weaknesses'] else 'minor issues'} immediately.
"""

        system_prompt = "You are a report formatter. Your ONLY job is to take the provided text and output it EXACTLY as written, ensuring the Markdown formatting is clean. DO NOT change ANY numbers, text, or examples."
        
        return self._call_groq_api([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])

    def _get_agent_issue(self, agent: Dict) -> str:
        if agent['script_errors'] > 0: return f"{agent['script_errors']} Script Errors"
        if agent['comprehension_issues'] > 0: return "Comprehension"
        if agent['rebuttal_no'] > 0: return "Skipped Rebuttal"
        return "Low Score"

    def _status(self, val: float) -> str:
        return "✅" if val >= 95 else "⚠️" if val >= 80 else "🔴"

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
