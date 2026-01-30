"""
LLM-Powered Campaign Performance Report Generator (ENHANCED)
Uses Groq (llama-3.1-8b-instant) to generate comprehensive campaign analysis
with TRANSCRIPT ANALYSIS, comprehension detection, script error flagging,
and tiered agent categorization.
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
    """Generates enhanced AI-powered campaign performance reports with transcript analysis."""
    
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
        """Call Groq API and return response text."""
        import requests
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,  # Lower temperature for consistent analysis
            "max_tokens": max_tokens
        }
        
        try:
            response = requests.post(self.base_url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"Groq API call failed: {e}")
            raise
    
    def _pre_analyze_transcripts(self, df: pd.DataFrame) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Pre-process transcripts to extract key insights for LLM context.
        
        Returns:
            Tuple of (insights dict, agent_issues dict)
        """
        insights = {
            'comprehension_issues': [],
            'script_errors': [],
            'pacing_issues': [],
            'rebuttal_quality': []
        }
        
        agent_issues = {}
        
        for idx, row in df.iterrows():
            agent = row.get('Agent Name', 'Unknown')
            transcript = str(row.get('Transcription', '')).lower()
            
            # Initialize agent tracking
            if agent not in agent_issues:
                agent_issues[agent] = {
                    'calls': 0,
                    'comprehension_issues': 0,
                    'script_errors': 0,
                    'pacing_issues': 0,
                    'good_rebuttals': 0,
                    'robotic_rebuttals': 0,
                    'issue_examples': []
                }
            
            agent_issues[agent]['calls'] += 1
            
            # 1. Comprehension Issues Detection
            comprehension_patterns = [
                (r"can'?t understand", "Customer couldn't understand agent"),
                (r"don'?t understand", "Customer didn't understand"),
                (r"pardon\??", "Customer asked to repeat"),
                (r"what\?+", "Customer confused"),
                (r"speak\s+(?:slower|clearer)", "Customer asked for clarity"),
                (r"i'?m?\s+sorry\s*\?", "Customer confused"),
                (r"what'?s?\s+this\s+about", "Customer unclear on purpose"),
                (r"say\s+that\s+again", "Customer asked to repeat"),
                (r"repeat\s+that", "Customer asked to repeat"),
                (r"huh\?+", "Customer confused")
            ]
            
            for pattern, description in comprehension_patterns:
                if re.search(pattern, transcript):
                    agent_issues[agent]['comprehension_issues'] += 1
                    # Extract context around the issue
                    match = re.search(pattern, transcript)
                    if match:
                        start = max(0, match.start() - 50)
                        end = min(len(transcript), match.end() + 50)
                        excerpt = transcript[start:end]
                        insights['comprehension_issues'].append({
                            'agent': agent,
                            'pattern': description,
                            'transcript_excerpt': f"...{excerpt}..."
                        })
                        agent_issues[agent]['issue_examples'].append(f"Comprehension: {excerpt}")
                    break
            
            # 2. Script Errors Detection
            script_errors = [
                ('interestted', 'interested'),
                ('sellling', 'selling'),
                ('profit interestt', 'property interest'),
                ('gardening the property', 'calling about the property'),
                ('displaying', 'buying'),
                ('propertty', 'property'),
                ('callingg', 'calling'),
                ('interrest', 'interest')
            ]
            
            for error, correction in script_errors:
                if error in transcript:
                    agent_issues[agent]['script_errors'] += 1
                    insights['script_errors'].append({
                        'agent': agent,
                        'error': error,
                        'correction': correction
                    })
                    agent_issues[agent]['issue_examples'].append(f"Script error: '{error}' should be '{correction}'")
                    break
            
            # 3. Pacing Issues Detection (long agent monologues)
            # Count consecutive agent speech without customer interaction
            lines = [l.strip() for l in transcript.split('\n') if l.strip()]
            agent_consecutive = 0
            max_consecutive = 0
            
            for line in lines:
                if any(line.startswith(prefix) for prefix in ['1a:', 'agent:', 'a:', '1 a:']):
                    agent_consecutive += 1
                    max_consecutive = max(max_consecutive, agent_consecutive)
                else:
                    agent_consecutive = 0
            
            if max_consecutive >= 3:  # Agent spoke 3+ times without customer response
                agent_issues[agent]['pacing_issues'] += 1
                insights['pacing_issues'].append({
                    'agent': agent,
                    'consecutive_lines': max_consecutive
                })
            
            # 4. Rebuttal Quality Analysis
            if row.get('Rebuttal Detection') == 'Yes':
                rebuttal_phrases = [
                    "since i got you",
                    "before i let you go",
                    "do you have any property",
                    "would you like to sell",
                    "any property you trying to sell",
                    "thinking about selling"
                ]
                
                natural_indicators = ["well,", "you know,", "actually,", "maybe", "by the way"]
                
                for phrase in rebuttal_phrases:
                    if phrase in transcript:
                        # Check if rebuttal sounds natural
                        start = transcript.find(phrase)
                        rebuttal_section = transcript[max(0, start-30):start+100]
                        
                        if any(ind in rebuttal_section for ind in natural_indicators):
                            agent_issues[agent]['good_rebuttals'] += 1
                            insights['rebuttal_quality'].append({
                                'agent': agent,
                                'quality': 'natural',
                                'phrase': rebuttal_section[:80]
                            })
                        else:
                            agent_issues[agent]['robotic_rebuttals'] += 1
                            insights['rebuttal_quality'].append({
                                'agent': agent,
                                'quality': 'robotic',
                                'phrase': rebuttal_section[:80]
                            })
                        break
        
        return insights, agent_issues
    
    def _calculate_agent_tiers(self, df: pd.DataFrame, agent_issues: Dict[str, Any]) -> Dict[str, List[Dict]]:
        """
        Categorize agents into performance tiers based on metrics AND transcript analysis.
        
        Returns:
            Dict with 'tier1', 'tier2', 'tier3' lists
        """
        tiers = {
            'tier1': [],  # Excellent: No issues in metadata OR transcription
            'tier2': [],  # Good with Issues: Good metadata but transcript issues
            'tier3': []   # Needs Coaching: Poor metadata AND transcript issues
        }
        
        if 'Agent Name' not in df.columns:
            return tiers
        
        for agent in df['Agent Name'].unique():
            agent_df = df[df['Agent Name'] == agent]
            agent_calls = len(agent_df)
            issues = agent_issues.get(agent, {})
            
            # Calculate metadata score
            late_hello_bad = 0
            releasing_bad = 0
            rebuttal_bad = 0
            avg_intro_score = 0
            
            if 'Late Hello Detection' in df.columns:
                late_hello_bad = len(agent_df[agent_df['Late Hello Detection'] == 'Yes'])
            if 'Releasing Detection' in df.columns:
                releasing_bad = len(agent_df[agent_df['Releasing Detection'] == 'Yes'])
            if 'Rebuttal Detection' in df.columns:
                rebuttal_bad = len(agent_df[agent_df['Rebuttal Detection'] == 'No'])
            if 'Intro Score' in df.columns:
                try:
                    scores = agent_df['Intro Score'].astype(str).str.replace('%', '').astype(float)
                    avg_intro_score = scores.mean()
                except:
                    avg_intro_score = 0
            
            # Calculate metadata performance (weighted)
            metadata_score = 0
            if agent_calls > 0:
                metadata_score = (
                    ((agent_calls - late_hello_bad) / agent_calls * 100) * 0.25 +
                    ((agent_calls - releasing_bad) / agent_calls * 100) * 0.25 +
                    ((agent_calls - rebuttal_bad) / agent_calls * 100) * 0.3 +
                    (avg_intro_score * 0.2)
                )
            
            # Calculate transcript score
            transcript_issues = (
                issues.get('comprehension_issues', 0) +
                issues.get('script_errors', 0) +
                issues.get('pacing_issues', 0)
            )
            transcript_score = max(0, 100 - (transcript_issues * 15))  # -15 per issue
            
            # Determine tier
            agent_data = {
                'name': agent,
                'calls': agent_calls,
                'metadata_score': round(metadata_score, 1),
                'transcript_score': round(transcript_score, 1),
                'late_hello_bad': late_hello_bad,
                'releasing_bad': releasing_bad,
                'rebuttal_bad': rebuttal_bad,
                'avg_intro_score': round(avg_intro_score, 1),
                'comprehension_issues': issues.get('comprehension_issues', 0),
                'script_errors': issues.get('script_errors', 0),
                'good_rebuttals': issues.get('good_rebuttals', 0),
                'issue_examples': issues.get('issue_examples', [])[:2]  # Top 2 examples
            }
            
            # Tier assignment logic
            if metadata_score >= 85 and transcript_score >= 85:
                tiers['tier1'].append(agent_data)
            elif metadata_score >= 70 and transcript_score < 85:
                tiers['tier2'].append(agent_data)
            else:
                tiers['tier3'].append(agent_data)
        
        # Sort each tier by combined score
        for tier in tiers:
            tiers[tier] = sorted(
                tiers[tier],
                key=lambda x: (x['metadata_score'] + x['transcript_score']) / 2,
                reverse=True
            )
        
        return tiers
    
    def _build_enhanced_prompt(self, campaign_name: str, df: pd.DataFrame, 
                                insights: Dict, agent_issues: Dict, 
                                tiers: Dict) -> List[Dict[str, str]]:
        """Build comprehensive prompt for enhanced LLM analysis."""
        
        total_calls = len(df)
        unique_agents = df['Agent Name'].nunique() if 'Agent Name' in df.columns else 0
        
        # Count issues
        comprehension_agents = sum(1 for a in agent_issues.values() if a.get('comprehension_issues', 0) > 0)
        script_error_agents = sum(1 for a in agent_issues.values() if a.get('script_errors', 0) > 0)
        total_comprehension = sum(a.get('comprehension_issues', 0) for a in agent_issues.values())
        total_script_errors = sum(a.get('script_errors', 0) for a in agent_issues.values())
        
        # Build KPI summary
        kpis = self._calculate_kpis(df)
        
        # Format tier information
        tier1_summary = "\n".join([
            f"- {a['name']}: {a['calls']} calls, {a['avg_intro_score']}% intro score, no issues"
            for a in tiers['tier1'][:5]
        ]) or "No agents in this tier"
        
        tier2_summary = "\n".join([
            f"- {a['name']}: {a['calls']} calls, {a['comprehension_issues']} comprehension issues, {a['script_errors']} script errors"
            for a in tiers['tier2'][:5]
        ]) or "No agents in this tier"
        
        tier3_summary = "\n".join([
            f"- {a['name']}: {a['calls']} calls, metadata={a['metadata_score']}%, transcript={a['transcript_score']}%"
            for a in tiers['tier3'][:5]
        ]) or "No agents in this tier"
        
        # Format specific issue examples
        issue_examples = ""
        if insights['comprehension_issues']:
            issue_examples += "\n**Comprehension Issue Examples:**\n"
            for issue in insights['comprehension_issues'][:3]:
                issue_examples += f"- {issue['agent']}: \"{issue['transcript_excerpt']}\"\n"
        
        if insights['script_errors']:
            issue_examples += "\n**Script Error Examples:**\n"
            error_counts = Counter([e['error'] for e in insights['script_errors']])
            for error, count in error_counts.most_common(3):
                correction = next(e['correction'] for e in insights['script_errors'] if e['error'] == error)
                issue_examples += f"- \"{error}\" ({count}x) → should be \"{correction}\"\n"
        
        user_prompt = f"""
# CAMPAIGN PERFORMANCE ANALYSIS - ENHANCED

## CAMPAIGN: {campaign_name}
## TOTAL CALLS: {total_calls}
## AGENTS AUDITED: {unique_agents}

---

## META-METRICS (Standard KPIs)

| Metric | Good | Bad | % Good |
|--------|------|-----|--------|
| Late Hello Detection | {kpis['late_hello']['good']} | {kpis['late_hello']['bad']} | {kpis['late_hello']['pct_good']}% |
| Releasing Detection | {kpis['releasing']['good']} | {kpis['releasing']['bad']} | {kpis['releasing']['pct_good']}% |
| Rebuttal Detection | {kpis['rebuttal']['good']} | {kpis['rebuttal']['bad']} | {kpis['rebuttal']['pct_good']}% |

---

## TRANSCRIPTION ANALYSIS (Pre-Analyzed)

**Agents with Comprehension Issues:** {comprehension_agents} agents ({total_comprehension} total incidents)
**Agents with Script Errors:** {script_error_agents} agents ({total_script_errors} total incidents)

{issue_examples}

---

## AGENT PERFORMANCE TIERS (Pre-Calculated)

### 🟢 TIER 1: Conversation Masters ({len(tiers['tier1'])} agents)
{tier1_summary}

### 🟡 TIER 2: Good But Unclear ({len(tiers['tier2'])} agents)
{tier2_summary}

### 🔴 TIER 3: Needs Coaching ({len(tiers['tier3'])} agents)
{tier3_summary}

---

## YOUR TASK

Generate a professional campaign performance report with the following structure:

### **Overall Campaign Summary**
- Total Calls Audited: {total_calls}
- Agents Audited: {unique_agents}

---

### **Key Performance Indicators (KPIs)**

| Metric | Good (No Issue) | Bad (Issue Found) | % Good |
|--------|-----------------|-------------------|---------|
[Fill with data from above]

[Add 2-3 sentences analyzing KPI results with ✅ and ⚠️ symbols]

---

### **📊 DUAL-LAYER ANALYSIS**

#### Transcription Insights
[Summarize comprehension issues and script errors found]
- Top issue found
- Agents most affected
- Pattern analysis

---

### **👥 AGENT PERFORMANCE TIERS**

#### 🟢 TIER 1: Conversation Masters
[For each agent: Name, Strengths, Example of excellent communication]

#### 🟡 TIER 2: Good But Unclear  
[For each agent: Name, Issue, Problematic phrase, Suggested fix, Training drill]

#### 🔴 TIER 3: Needs Coaching
[For each agent: Name, Multiple issues, Immediate action plan]

---

### **Agent-Level Performance Breakdown**

| Agent Name | Calls | Late Hello | Releasing | Rebuttal Skipped | Intro Score | Clarity Score | Status |
|------------|-------|------------|-----------|------------------|-------------|---------------|--------|
[Fill table with agent data, Clarity Score = 100 - (comprehension_issues * 15)]

---

### **Rebuttal Analysis**
- Calls with Rebuttals: X/Y (Z%)
- Natural vs Robotic rebuttals
- Best rebuttal phrases observed

---

### **Lowest Performing Agents**
[List bottom 2-3 agents with specific issues and coaching plan]

---

### **Conclusion: Are Agents Doing Their Best?**
[2-3 sentence assessment using ✅ and ⚠️]

**Areas for Improvement:**
- [Bullet list]

---

### **🛠 ACTION PLAN**

**Week 1 Priority:**
1. [First priority with specific agent names]
2. [Second priority]

**Training Focus:**
- [Specific training topic]
- [Specific drill]

**Success Metrics:**
- Reduce comprehension issues by X%
- Improve average call clarity by X%

---

IMPORTANT FORMATTING:
- Use markdown tables EXACTLY as shown
- Include ✅ and ⚠️ symbols for visual clarity
- Quote actual problematic phrases when available
- Be specific with agent names and recommendations
- Keep the same structure order as outlined above
"""
        
        system_prompt = """You are a call center performance analyst with expertise in:
1. Call quality analysis
2. Speech clarity evaluation  
3. Sales script optimization
4. Agent coaching strategy

You analyze BOTH metadata AND transcription content to provide actionable insights.
Be specific, data-driven, and actionable. Quote actual phrases from data when available.
Format output in clean markdown with tables and visual indicators (✅, ⚠️, 🟢, 🟡, 🔴)."""
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    
    def _calculate_kpis(self, df: pd.DataFrame) -> Dict[str, Dict]:
        """Calculate KPI metrics from dataframe."""
        total_calls = len(df)
        
        kpis = {
            'late_hello': {'good': total_calls, 'bad': 0, 'pct_good': 100.0},
            'releasing': {'good': total_calls, 'bad': 0, 'pct_good': 100.0},
            'rebuttal': {'good': total_calls, 'bad': 0, 'pct_good': 100.0}
        }
        
        if 'Late Hello Detection' in df.columns:
            bad = len(df[df['Late Hello Detection'] == 'Yes'])
            kpis['late_hello'] = {
                'good': total_calls - bad,
                'bad': bad,
                'pct_good': round((total_calls - bad) / total_calls * 100, 1) if total_calls > 0 else 0
            }
        
        if 'Releasing Detection' in df.columns:
            bad = len(df[df['Releasing Detection'] == 'Yes'])
            kpis['releasing'] = {
                'good': total_calls - bad,
                'bad': bad,
                'pct_good': round((total_calls - bad) / total_calls * 100, 1) if total_calls > 0 else 0
            }
        
        if 'Rebuttal Detection' in df.columns:
            bad = len(df[df['Rebuttal Detection'] == 'No'])
            kpis['rebuttal'] = {
                'good': total_calls - bad,
                'bad': bad,
                'pct_good': round((total_calls - bad) / total_calls * 100, 1) if total_calls > 0 else 0
            }
        
        return kpis
    
    def generate_report(self, df: pd.DataFrame, campaign_name: str) -> str:
        """
        Generate enhanced AI-powered campaign performance report with transcript analysis.
        
        Args:
            df: Campaign audit dataframe with call data
            campaign_name: Name of the campaign
        
        Returns:
            Markdown-formatted comprehensive report
        """
        try:
            logger.info(f"Generating ENHANCED AI report for campaign: {campaign_name}")
            
            if df.empty:
                return "❌ **Error:** No data available to generate report."
            
            # Step 1: Pre-analyze transcripts
            logger.info("Step 1: Pre-analyzing transcripts...")
            insights, agent_issues = self._pre_analyze_transcripts(df)
            
            # Step 2: Calculate agent tiers
            logger.info("Step 2: Calculating agent performance tiers...")
            tiers = self._calculate_agent_tiers(df, agent_issues)
            
            # Step 3: Build enhanced prompt
            logger.info("Step 3: Building enhanced prompt...")
            messages = self._build_enhanced_prompt(campaign_name, df, insights, agent_issues, tiers)
            
            # Step 4: Call Groq API
            logger.info("Step 4: Calling Groq API...")
            report = self._call_groq_api(messages, max_tokens=4000)
            
            # Add metadata header
            timestamp = datetime.now().strftime("%Y-%m-%d %I:%M %p")
            header = f"# 🤖 Campaign Performance Report - ENHANCED\n\n"
            header += f"**Campaign:** {campaign_name}  \n"
            header += f"**Generated:** {timestamp}  \n"
            header += f"**Powered by:** Groq AI (llama-3.1-8b-instant) + Transcript Analysis  \n"
            header += f"**Analysis Features:** Comprehension Detection | Script Error Flagging | Agent Tiering  \n\n"
            header += "---\n\n"
            
            full_report = header + report
            
            logger.info(f"Successfully generated enhanced report for {campaign_name}")
            return full_report
            
        except Exception as e:
            logger.error(f"Failed to generate enhanced campaign report: {e}", exc_info=True)
            return f"❌ **Error generating report:** {str(e)}\n\nPlease check your Groq API key and internet connection."


# Singleton instance for easy import
_report_generator = None

def get_report_generator() -> CampaignReportGenerator:
    """Get singleton campaign report generator instance."""
    global _report_generator
    if _report_generator is None:
        _report_generator = CampaignReportGenerator()
    return _report_generator
