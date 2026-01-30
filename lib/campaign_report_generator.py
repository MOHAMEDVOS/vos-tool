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
        Build prompt with PRE-CALCULATED statistics to prevent LLM hallucination.
        """
        
        # Format agent table data
        agent_table = "| Agent Name | Calls | Late Hello (Bad) | Releasing (Bad) | Rebuttal Skipped | Intro Score | Status | Tier |\n"
        agent_table += "|------------|-------|------------------|-----------------|------------------|-------------|--------|------|\n"
        
        for agent in agent_data:
            agent_table += f"| {agent['name']} | {agent['calls']} | {agent['late_hello_bad']} | {agent['releasing_bad']} | {agent['rebuttal_no']} | {agent['avg_intro_score']}% | {agent['common_status']} | {agent['tier']} |\n"
        
        # Format comprehension examples
        comp_examples = ""
        if issues['comprehension_examples']:
            comp_examples = "**Actual Comprehension Issues Found:**\n"
            for ex in issues['comprehension_examples'][:3]:
                comp_examples += f"- **{ex['agent']}**: \"{ex['excerpt']}\"\n"
        
        # Format script error examples
        script_examples = ""
        if issues['script_error_examples']:
            script_examples = "**Actual Script Errors Found:**\n"
            for ex in issues['script_error_examples'][:3]:
                script_examples += f"- **{ex['agent']}**: \"{ex['error']}\" → should be \"{ex['correction']}\"\n"
        
        # Agents who skipped rebuttals
        rebuttal_skippers = [a for a in agent_data if a['rebuttal_no'] > 0]
        rebuttal_skipper_text = ""
        if rebuttal_skippers:
            rebuttal_skipper_text = "**Agents who skipped rebuttals:**\n"
            for a in rebuttal_skippers:
                rebuttal_skipper_text += f"- {a['name']}: skipped {a['rebuttal_no']} time(s)\n"
        
        # Tier summaries
        tier1 = [a for a in agent_data if '🟢' in a['tier']]
        tier2 = [a for a in agent_data if '🟡' in a['tier']]
        tier3 = [a for a in agent_data if '🔴' in a['tier']]
        
        user_prompt = f"""
# CAMPAIGN PERFORMANCE REPORT - DATA-ACCURATE ANALYSIS

## ⚠️ CRITICAL INSTRUCTIONS - READ CAREFULLY
1. USE ONLY THE PRE-CALCULATED STATISTICS BELOW
2. DO NOT MAKE UP NUMBERS - all stats are already calculated
3. DO NOT INVENT METRICS like "Clarity Score" or "Metadata Score"
4. These are OUTBOUND calls - agents call customers, not receive calls
5. Quote ONLY the transcript excerpts provided below
6. NO generic examples like "thank you for calling"

---

## PRE-CALCULATED STATISTICS (USE THESE EXACT NUMBERS)

**Campaign:** {campaign_name}
**Total Calls:** {stats['total_calls']}
**Agents Audited:** {stats['unique_agents']}

### KPI Table (ALREADY CALCULATED):
| Metric | Good (No Issue) | Bad (Issue Found) | % Good |
|--------|-----------------|-------------------|---------|
| **Late Hello Detection** | {stats['late_hello']['good']} | {stats['late_hello']['bad']} | {stats['late_hello']['pct_good']}% |
| **Releasing Detection** | {stats['releasing']['good']} | {stats['releasing']['bad']} | {stats['releasing']['pct_good']}% |
| **Rebuttal Detection** | {stats['rebuttal']['yes']} | {stats['rebuttal']['no']} | {stats['rebuttal']['pct_yes']}% |

### Rebuttal Statistics:
- **Calls WITH Rebuttals:** {stats['rebuttal']['yes']}/{stats['total_calls']} ({stats['rebuttal']['pct_yes']}%)
- **Calls WITHOUT Rebuttals:** {stats['rebuttal']['no']}/{stats['total_calls']}
{rebuttal_skipper_text}

---

## TRANSCRIPT ANALYSIS (REAL ISSUES FOUND)

**Comprehension Issues:** {issues['comprehension_count']} total incidents across {len(issues['comprehension_agents'])} agents
{comp_examples}

**Script Errors:** {issues['script_error_count']} total incidents across {len(issues['script_error_agents'])} agents
{script_examples}

---

## AGENT PERFORMANCE DATA (PRE-CALCULATED)

{agent_table}

### Agent Tiers:
- **🟢 Tier 1 (No Issues):** {len(tier1)} agents
- **🟡 Tier 2 (Minor Issues):** {len(tier2)} agents
- **🔴 Tier 3 (Needs Coaching):** {len(tier3)} agents

---

## YOUR TASK

Using ONLY the pre-calculated data above, generate a professional report with this structure:

### **Overall Campaign Summary**
- Total Calls Audited: {stats['total_calls']}
- Agents Audited: {stats['unique_agents']}

---

### **Key Performance Indicators (KPIs)**
[Copy the KPI table exactly as provided above]
[Add 2-3 sentences analyzing results using ✅ and ⚠️]

---

### **Transcription Insights**
[Summarize the comprehension and script issues using the EXACT counts provided]
[Quote ONLY the examples provided above - DO NOT make up new ones]

---

### **👥 Agent Performance Tiers**

#### 🟢 TIER 1: Clean Performers ({len(tier1)} agents)
[List agents with no issues, use data from table above]

#### 🟡 TIER 2: Minor Issues ({len(tier2)} agents)
[For each agent: specific issue from their row, recommendation]

#### 🔴 TIER 3: Needs Coaching ({len(tier3)} agents)
[For each agent: issues, coaching plan]

---

### **Agent-Level Performance Breakdown**
[Copy the agent table exactly as provided above]

---

### **Rebuttal Analysis**
- Calls with Rebuttals: {stats['rebuttal']['yes']}/{stats['total_calls']} ({stats['rebuttal']['pct_yes']}%)
- Calls without Rebuttals: {stats['rebuttal']['no']}/{stats['total_calls']}
[List agents who skipped rebuttals using EXACT data above]

---

### **Lowest Performing Agents**
[Use data from Tier 3 agents above - quote specific issues]

---

### **Conclusion**
[Brief assessment using ✅ and ⚠️ based on the actual numbers]

---

### **🛠 ACTION PLAN**
[Specific recommendations based on REAL issues found]
- Week 1: Fix script errors ({issues['script_error_count']} incidents)
- Training focus: Agents with comprehension issues
- Success metric: Reduce issues by specific percentage

---

REMEMBER: ALL STATISTICS MUST MATCH THE NUMBERS PROVIDED ABOVE EXACTLY.
"""
        
        system_prompt = """You are a call center performance analyst creating a data-accurate report.

CRITICAL RULES:
1. USE ONLY the pre-calculated statistics provided - do not calculate your own
2. DO NOT invent metrics (no "Clarity Score", "Metadata Score", etc.)
3. These are OUTBOUND sales calls - agents CALL customers, they don't receive calls
4. Quote ONLY the transcript excerpts provided - no generic examples
5. All numbers must match the pre-calculated data exactly
6. Format output in clean markdown with the tables provided

You are formatting and presenting pre-analyzed data, not creating new analysis."""
        
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
