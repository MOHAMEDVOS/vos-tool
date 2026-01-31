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
    
    def _call_groq_api(self, messages: List[Dict[str, str]], max_tokens: int = 4000) -> str:
        """Call Groq API with strict temperature settings to prevent hallucinations."""
        import requests
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.05,  # Very low - nearly deterministic
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
        """
        Calculate ALL statistics from actual data BEFORE sending to LLM.
        This prevents hallucination by giving the LLM pre-verified numbers.
        """
        total_calls = len(df)
        unique_agents = df['Agent Name'].nunique() if 'Agent Name' in df.columns else 0
        
        stats = {
            'total_calls': total_calls,
            'unique_agents': unique_agents,
            'columns_available': list(df.columns),
            'agent_names': df['Agent Name'].unique().tolist() if 'Agent Name' in df.columns else []
        }
        
        # KPIs - calculate from actual data
        if 'Late Hello Detection' in df.columns:
            late_hello_bad = len(df[df['Late Hello Detection'] == 'Yes'])
            stats['late_hello'] = {
                'good': total_calls - late_hello_bad,
                'bad': late_hello_bad,
                'pct_good': round((total_calls - late_hello_bad) / total_calls * 100, 1) if total_calls > 0 else 0
            }
        else:
            stats['late_hello'] = {'good': total_calls, 'bad': 0, 'pct_good': 100.0}
        
        if 'Releasing Detection' in df.columns:
            releasing_bad = len(df[df['Releasing Detection'] == 'Yes'])
            stats['releasing'] = {
                'good': total_calls - releasing_bad,
                'bad': releasing_bad,
                'pct_good': round((total_calls - releasing_bad) / total_calls * 100, 1) if total_calls > 0 else 0
            }
        else:
            stats['releasing'] = {'good': total_calls, 'bad': 0, 'pct_good': 100.0}
        
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
    
    def _extract_real_transcript_issues(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Scan actual transcripts for issues - count and extract REAL examples only.
        """
        issues = {
            'comprehension_count': 0,
            'comprehension_agents': {},
            'comprehension_examples': [],
            'script_error_count': 0,
            'script_error_agents': {},
            'script_error_examples': [],
            'real_transcript_excerpts': []
        }
        
        if 'Transcription' not in df.columns:
            return issues
        
        # Comprehension issue patterns
        comprehension_patterns = [
            r"can'?t understand",
            r"don'?t understand",
            r"pardon\??",
            r"what'?s?\s+this\s+about",
            r"say\s+that\s+again",
            r"repeat\s+that"
        ]
        
        # Script error patterns
        script_errors = [
            ('interestted', 'interested'),
            ('sellling', 'selling'),
            ('profit interestt', 'property interest'),
            ('propertty', 'property'),
            ('interrest', 'interest')
        ]
        
        for idx, row in df.iterrows():
            agent = row.get('Agent Name', 'Unknown')
            transcript = str(row.get('Transcription', '')).lower()
            
            if not transcript or transcript == 'nan':
                continue
            
            # Check comprehension issues
            for pattern in comprehension_patterns:
                matches = re.findall(pattern, transcript)
                if matches:
                    issues['comprehension_count'] += len(matches)
                    if agent not in issues['comprehension_agents']:
                        issues['comprehension_agents'][agent] = 0
                    issues['comprehension_agents'][agent] += len(matches)
                    
                    # Extract actual excerpt
                    match = re.search(pattern, transcript)
                    if match and len(issues['comprehension_examples']) < 5:
                        start = max(0, match.start() - 30)
                        end = min(len(transcript), match.end() + 30)
                        excerpt = transcript[start:end]
                        issues['comprehension_examples'].append({
                            'agent': agent,
                            'excerpt': f"...{excerpt}..."
                        })
            
            # Check script errors
            for error, correction in script_errors:
                if error in transcript:
                    issues['script_error_count'] += 1
                    if agent not in issues['script_error_agents']:
                        issues['script_error_agents'][agent] = []
                    if error not in issues['script_error_agents'][agent]:
                        issues['script_error_agents'][agent].append(error)
                    
                    if len(issues['script_error_examples']) < 5:
                        # Find context around the error
                        start = transcript.find(error)
                        excerpt = transcript[max(0, start-20):min(len(transcript), start+40)]
                        issues['script_error_examples'].append({
                            'agent': agent,
                            'error': error,
                            'correction': correction,
                            'excerpt': f"...{excerpt}..."
                        })
            
            # Extract sample transcript excerpts (first 50 chars per agent)
            if agent not in [e['agent'] for e in issues['real_transcript_excerpts']]:
                sample = transcript[:100] if len(transcript) > 100 else transcript
                issues['real_transcript_excerpts'].append({
                    'agent': agent,
                    'sample': sample
                })
        
        return issues
    
    def _calculate_agent_performance(self, df: pd.DataFrame, issues: Dict) -> List[Dict]:
        """
        Calculate per-agent performance from ACTUAL data only.
        No made-up metrics like "Clarity Score" - only what exists in columns.
        """
        agent_data = []
        
        if 'Agent Name' not in df.columns:
            return agent_data
        
        for agent in df['Agent Name'].unique():
            agent_df = df[df['Agent Name'] == agent]
            agent_calls = len(agent_df)
            
            data = {
                'name': agent,
                'calls': agent_calls,
                'late_hello_bad': 0,
                'releasing_bad': 0,
                'rebuttal_no': 0,
                'rebuttal_yes': 0,
                'avg_intro_score': 0,
                'common_status': 'N/A',
                'comprehension_issues': issues['comprehension_agents'].get(agent, 0),
                'script_errors': len(issues['script_error_agents'].get(agent, []))
            }
            
            if 'Late Hello Detection' in df.columns:
                data['late_hello_bad'] = len(agent_df[agent_df['Late Hello Detection'] == 'Yes'])
            
            if 'Releasing Detection' in df.columns:
                data['releasing_bad'] = len(agent_df[agent_df['Releasing Detection'] == 'Yes'])
            
            if 'Rebuttal Detection' in df.columns:
                data['rebuttal_no'] = len(agent_df[agent_df['Rebuttal Detection'] == 'No'])
                data['rebuttal_yes'] = len(agent_df[agent_df['Rebuttal Detection'] == 'Yes'])
            
            if 'Intro Score' in df.columns:
                try:
                    scores = agent_df['Intro Score'].astype(str).str.replace('%', '').astype(float)
                    data['avg_intro_score'] = round(scores.mean(), 1)
                except:
                    data['avg_intro_score'] = 0
            
            if 'Status' in df.columns:
                try:
                    data['common_status'] = agent_df['Status'].mode()[0]
                except:
                    data['common_status'] = 'N/A'
            
            # Determine tier based on REAL issues only
            total_issues = (
                data['late_hello_bad'] + 
                data['releasing_bad'] + 
                data['rebuttal_no'] +
                data['comprehension_issues'] +
                data['script_errors']
            )
            
            if total_issues == 0:
                data['tier'] = '🟢 Tier 1'
            elif total_issues <= 2:
                data['tier'] = '🟡 Tier 2'
            else:
                data['tier'] = '🔴 Tier 3'
            
            agent_data.append(data)
        
        # Sort by total issues (best performers first)
        agent_data.sort(key=lambda x: (
            x['late_hello_bad'] + x['releasing_bad'] + x['rebuttal_no'] + x['comprehension_issues']
        ))
        
        return agent_data
    
    def _build_accurate_prompt(self, campaign_name: str, stats: Dict, 
                                issues: Dict, agent_data: List[Dict]) -> List[Dict[str, str]]:
        """
        Build prompt with PRE-CALCULATED statistics matching user's desired format.
        """
        
        # Calculate average intro score
        avg_intro = sum(a['avg_intro_score'] for a in agent_data) / len(agent_data) if agent_data else 0
        
        # Find top performer
        top_agent = max(agent_data, key=lambda x: x['avg_intro_score']) if agent_data else None
        
        # Tier summaries
        tier1 = [a for a in agent_data if '🟢' in a['tier']]
        tier2 = [a for a in agent_data if '🟡' in a['tier']]
        tier3 = [a for a in agent_data if '🔴' in a['tier']]
        
        # Build tier tables
        tier1_table = ""
        if tier1:
            tier1_table = "| Agent | Calls | Score | Strength |\n|-------|-------|-------|----------|\n"
            for a in tier1[:5]:
                tier1_table += f"| {a['name']} | {a['calls']} | {a['avg_intro_score']}% | Consistent quality |\n"
        
        tier2_table = ""
        if tier2:
            tier2_table = "| Agent | Calls | Issue | Action Needed |\n|-------|-------|-------|---------------|\n"
            for a in tier2[:5]:
                issue = ""
                if a['comprehension_issues'] > 0:
                    issue = f"{a['comprehension_issues']} comprehension issues"
                elif a['script_errors'] > 0:
                    issue = f"Script errors in {a['script_errors']} calls"
                elif a['rebuttal_no'] > 0:
                    issue = "Skipped rebuttal"
                else:
                    issue = f"Low intro score ({a['avg_intro_score']}%)"
                tier2_table += f"| {a['name']} | {a['calls']} | {issue} | Coaching needed |\n"
        
        tier3_table = ""
        if tier3:
            tier3_table = "| Agent | Calls | Issue | Action |\n|-------|-------|-------|--------|\n"
            for a in tier3[:5]:
                issues_list = []
                if a['comprehension_issues'] > 0:
                    issues_list.append(f"{a['comprehension_issues']} comprehension")
                if a['script_errors'] > 0:
                    issues_list.append(f"{a['script_errors']} script errors")
                if a['rebuttal_no'] > 0:
                    issues_list.append(f"{a['rebuttal_no']} skipped rebuttals")
                issue_text = ", ".join(issues_list) if issues_list else "Multiple issues"
                tier3_table += f"| {a['name']} | {a['calls']} | {issue_text} | 1:1 coaching |\n"
        
        # Format script error details
        script_error_details = ""
        if issues['script_error_examples']:
            ex = issues['script_error_examples'][0]
            script_error_details = f"""
**Example:** "{ex['error']}" in transcripts
**Fix:** "{ex['correction']}"
**Affects:** {', '.join([e['agent'] for e in issues['script_error_examples'][:3]])}
"""
        
        # Format comprehension details
        comp_details = ""
        if issues['comprehension_examples']:
            ex = issues['comprehension_examples'][0]
            comp_details = f"""
**Example:** Customer said "I can't understand you"
**Root Cause:** Fast speech, unclear pronunciation
**Affects:** {', '.join([e['agent'] for e in issues['comprehension_examples'][:3]])}
"""
        
        user_prompt = f"""
# CAMPAIGN PERFORMANCE REPORT - EXECUTIVE DASHBOARD FORMAT

## DATA PROVIDED (USE THESE EXACT NUMBERS):

**Campaign:** {campaign_name}
**Total Calls:** {stats['total_calls']}
**Agents:** {stats['unique_agents']}
**Average Intro Score:** {avg_intro:.0f}%
**Top Performer:** {top_agent['name'] if top_agent else 'N/A'} ({top_agent['avg_intro_score'] if top_agent else 0}%)

**KPIs:**
- Late Hello: {stats['late_hello']['pct_good']}% good
- Releasing: {stats['releasing']['pct_good']}% good
- Rebuttal Usage: {stats['rebuttal']['pct_yes']}%

**Issues Found:**
- Comprehension Issues: {issues['comprehension_count']} incidents
- Script Errors: {issues['script_error_count']} incidents
- Rebuttals Skipped: {stats['rebuttal']['no']} calls

**Agent Tiers:**
- 🟢 Top Performers: {len(tier1)} agents
- 🟡 Needs Coaching: {len(tier2)} agents
- 🔴 Urgent Attention: {len(tier3)} agents

---

## YOUR TASK: Generate report in THIS EXACT FORMAT:

```
🚀 CAMPAIGN PERFORMANCE DASHBOARD
Campaign: {campaign_name}
Generated: [Current Date]
Calls Analyzed: {stats['total_calls']} calls | Agents: {stats['unique_agents']}

📊 EXECUTIVE SUMMARY
Overall Status: [🟢 Excellent / 🟡 Good with Room for Improvement / 🔴 Needs Attention]

| ✅ Strengths | ⚠️ Areas Needing Attention |
|--------------|----------------------------|
| [List 2-3 strengths based on data] | [List 2-3 areas needing work] |

🎯 KEY METRICS AT A GLANCE
```
🔊 CALL QUALITY
├── Prompt Answering: {stats['late_hello']['pct_good']}% [✅/⚠️]
├── Professional Endings: {stats['releasing']['pct_good']}% [✅/⚠️]
└── Rebuttal Usage: {stats['rebuttal']['pct_yes']}% [✅/⚠️]

🎤 COMMUNICATION
├── Script Accuracy: [Calculate from script errors]
└── Customer Understanding: [Calculate from comprehension issues]

👥 TEAM PERFORMANCE
├── Top Agent: {top_agent['name'] if top_agent else 'N/A'} ({top_agent['avg_intro_score'] if top_agent else 0}%)
├── Average Score: {avg_intro:.0f}%
└── Needs Help: {len(tier3)} agents
```

👥 AGENT PERFORMANCE TIERS

🏆 TOP PERFORMERS ({len(tier1)} agents)
{tier1_table}

🔧 NEEDS COACHING ({len(tier2)} agents)
{tier2_table}

⚠️ URGENT ATTENTION ({len(tier3)} agents)
{tier3_table}

🚨 TOP 3 ISSUES IDENTIFIED

1️⃣ [BIGGEST ISSUE] ([count] incidents) [🔴/🟡]
**What:** [Description]
**Example:** [Quote from data]
**Fix:** [Specific correction]
**Affects:** [Agent names]

2️⃣ [SECOND ISSUE] ([count] incidents) [🔴/🟡]
**What:** [Description]
**Example:** [Quote from data]
**Root Cause:** [Analysis]
**Fix:** [Specific action]

3️⃣ [THIRD ISSUE] ([count] incidents) [🔴/🟡]
**What:** [Description]
**Affects:** [Agent names]
**Fix:** [Specific action]

📈 DETAILED PERFORMANCE BREAKDOWN

📞 Call Quality Metrics
| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Prompt Answering | 100% | {stats['late_hello']['pct_good']}% | [✅/⚠️/🔴] |
| Professional Endings | 100% | {stats['releasing']['pct_good']}% | [✅/⚠️/🔴] |
| Rebuttal Usage | 95% | {stats['rebuttal']['pct_yes']}% | [✅/⚠️/🔴] |
| Script Accuracy | 95% | [Calculate]% | [✅/⚠️/🔴] |
| Customer Understanding | 95% | [Calculate]% | [✅/⚠️/🔴] |

👥 Agent-by-Agent Performance
| Agent | Calls | Intro Score | Rebuttals | Issues | Tier |
|-------|-------|-------------|-----------|--------|------|
[Fill with actual agent data]

🛠️ ACTION PLAN - WEEK 1

✅ TODAY (Priority Actions)
**[Action 1]**
- Update: [Specific change]
- Responsible: [Team/Person]
- Deadline: End of day

**[Action 2]**
- [Details]
- Time: This afternoon

✅ THIS WEEK (Training Schedule)
| Day | Time | Topic | Who |
|-----|------|-------|-----|
| Mon | 3:00 PM | [Topic] | [Agents] |
| Tue | 10:00 AM | [Topic] | All agents |
| Wed | 11:00 AM | [Topic] | [Specific agents] |

✅ PROCESS IMPROVEMENTS
- [Improvement 1] - [Description]
- [Improvement 2] - [Description]
- [Improvement 3] - [Description]

📈 SUCCESS METRICS & GOALS
| Goal | Current | Target (Next Week) | How We'll Measure |
|------|---------|-------------------|-------------------|
| [Metric 1] | [Current %] | [Target %] | [Method] |
| [Metric 2] | [Current %] | [Target %] | [Method] |

**Success Criteria:**
- [Criterion 1]
- [Criterion 2]
- [Criterion 3]

💡 KEY INSIGHTS & RECOMMENDATIONS

🎯 What's Working:
• [Strength 1]
• [Strength 2]
• [Strength 3]

🔧 Immediate Fixes:
**[Fix 1]** - [Description]
**[Fix 2]** - [Description]
**[Fix 3]** - [Description]
```

---

## CRITICAL FORMATTING RULES:
1. Use EXACT numbers from data provided above
2. Use emoji indicators: ✅ (good), ⚠️ (warning), 🔴 (urgent)
3. Create visual tree structure with ├── and └──
4. Use tables for structured data
5. Quote ONLY real examples from transcript data
6. NO made-up metrics or examples
7. Keep format EXACTLY as shown above
"""
        
        system_prompt = """You are a call center performance analyst creating an executive dashboard report.

CRITICAL RULES:
1. Follow the EXACT format provided in the template
2. Use ONLY the pre-calculated statistics - no new calculations
3. Use emoji indicators for visual clarity (✅ ⚠️ 🔴 🟢 🟡)
4. Create ASCII tree structures for metrics (├── └──)
5. Quote ONLY real examples from the data provided
6. NO hallucinations - all numbers must match the data exactly
7. These are OUTBOUND calls - agents call customers

Your goal is to create a visually appealing, executive-ready dashboard report."""
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    
    def _validate_report(self, report: str, stats: Dict) -> Tuple[bool, List[str]]:
        """
        Validate LLM output against actual data to catch hallucinations.
        """
        errors = []
        
        # Check total calls mentioned
        total_calls_str = str(stats['total_calls'])
        if total_calls_str not in report:
            errors.append(f"❌ Missing correct total calls ({total_calls_str})")
        
        # Check rebuttal percentage is reasonable
        rebuttal_pct = stats['rebuttal']['pct_yes']
        rebuttal_pct_str = str(rebuttal_pct)
        if rebuttal_pct_str not in report and str(round(rebuttal_pct)) not in report:
            # Check if it's close
            if "12%" in report or "13%" in report or "15%" in report:
                errors.append(f"❌ Wrong rebuttal rate (should be {rebuttal_pct}%, not 12-15%)")
        
        # Check for hallucinated metrics
        hallucination_phrases = [
            "clarity score",
            "metadata score", 
            "transcript score",
            "thank you for calling",
            "how can i help you",
            "how may i assist"
        ]
        
        report_lower = report.lower()
        for phrase in hallucination_phrases:
            if phrase in report_lower:
                errors.append(f"❌ Hallucination detected: '{phrase}' not in data")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def generate_report(self, df: pd.DataFrame, campaign_name: str) -> str:
        """
        Generate accurate AI-powered campaign performance report.
        Pre-calculates all statistics to prevent LLM hallucination.
        """
        try:
            logger.info(f"Generating ACCURATE AI report for campaign: {campaign_name}")
            
            if df.empty:
                return "❌ **Error:** No data available to generate report."
            
            # Step 1: Calculate REAL statistics from data
            logger.info("Step 1: Calculating real statistics from data...")
            stats = self._calculate_real_statistics(df)
            
            # Step 2: Extract REAL transcript issues
            logger.info("Step 2: Extracting real transcript issues...")
            issues = self._extract_real_transcript_issues(df)
            
            # Step 3: Calculate per-agent performance
            logger.info("Step 3: Calculating agent performance...")
            agent_data = self._calculate_agent_performance(df, issues)
            
            # Step 4: Build accurate prompt with pre-calculated data
            logger.info("Step 4: Building prompt with pre-calculated data...")
            messages = self._build_accurate_prompt(campaign_name, stats, issues, agent_data)
            
            # Step 5: Call Groq API
            logger.info("Step 5: Calling Groq API...")
            report = self._call_groq_api(messages, max_tokens=4000)
            
            # Step 6: Validate output
            logger.info("Step 6: Validating report accuracy...")
            is_valid, errors = self._validate_report(report, stats)
            
            # Add metadata header
            timestamp = datetime.now().strftime("%Y-%m-%d %I:%M %p")
            header = f"# 🤖 Campaign Performance Report\n\n"
            header += f"**Campaign:** {campaign_name}  \n"
            header += f"**Generated:** {timestamp}  \n"
            header += f"**Powered by:** Groq AI (llama-3.1-8b-instant)  \n"
            
            if not is_valid:
                header += f"\n**⚠️ Validation Warnings:**  \n"
                for error in errors:
                    header += f"- {error}  \n"
            
            header += "\n---\n\n"
            
            full_report = header + report
            
            logger.info(f"Report generated {'with warnings' if not is_valid else 'successfully'}")
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
