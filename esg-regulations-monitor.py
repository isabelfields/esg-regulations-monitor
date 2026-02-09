#!/usr/bin/env python3
"""
ESG Regulations Monitor - Official Sources Only
Monitors government and regulatory body announcements for ESG compliance requirements
"""

import feedparser
import json
import smtplib
import os
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import re

# Email configuration from environment variables
EMAIL_FROM = os.environ.get('EMAIL_FROM', '')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', '')
EMAIL_TO = os.environ.get('EMAIL_TO', '')

class ESGMonitor:
    def __init__(self):
        self.regulations_file = Path('regulations.json')
        self.dashboard_file = Path('esg-regulations-monitor.html')
        self.regulations = self.load_regulations()
    
    def load_regulations(self):
        """Load existing regulations from JSON file"""
        if self.regulations_file.exists():
            try:
                with open(self.regulations_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading regulations: {e}")
                return []
        return []
    
    def save_regulations(self):
        """Save regulations to JSON file"""
        try:
            with open(self.regulations_file, 'w', encoding='utf-8') as f:
                json.dump(self.regulations, f, indent=2, ensure_ascii=False)
            print(f"Saved {len(self.regulations)} regulations to {self.regulations_file}")
        except Exception as e:
            print(f"Error saving regulations: {e}")
    
    def parse_date(self, date_str):
        """Parse various date formats to YYYY-MM-DD"""
        if not date_str:
            return datetime.now().strftime('%Y-%m-%d')
        
        try:
            # Try common date formats
            for fmt in ['%a, %d %b %Y %H:%M:%S %Z', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%d']:
                try:
                    dt = datetime.strptime(date_str.split('.')[0].split('+')[0].strip(), fmt)
                    return dt.strftime('%Y-%m-%d')
                except:
                    continue
            
            # If all else fails, return today
            return datetime.now().strftime('%Y-%m-%d')
        except:
            return datetime.now().strftime('%Y-%m-%d')
    
    def is_recent_enough(self, date_string):
        """Check if regulation is from Jan 1, 2025 or later"""
        try:
            reg_date = datetime.strptime(date_string, '%Y-%m-%d')
            cutoff_date = datetime(2025, 1, 1)
            return reg_date >= cutoff_date
        except:
            return True
    
    def categorize_priority(self, title, description):
        """Determine priority level"""
        text = f"{title} {description}".lower()
        
        if any(word in text for word in ['final rule', 'adopted', 'enacted', 'effective', 'injunction', 'lawsuit', 'court order']):
            return 'critical'
        elif any(word in text for word in ['proposed', 'draft', 'consultation', 'comment period']):
            return 'high'
        else:
            return 'medium'
    
    def categorize_type(self, title, description):
        """Categorize regulation type"""
        text = f"{title} {description}".lower()
        
        if 'disclosure' in text or 'reporting' in text:
            return 'disclosure'
        elif 'enforcement' in text or 'lawsuit' in text or 'settlement' in text:
            return 'enforcement'
        elif 'guidance' in text or 'guidance' in text:
            return 'reporting'
        else:
            return 'reporting'
    
    def extract_tags(self, title, description):
        """Extract relevant tags"""
        text = f"{title} {description}".lower()
        tags = []
        
        tag_patterns = {
            'Climate': ['climate', 'ghg', 'greenhouse gas', 'emissions'],
            'Scope 3': ['scope 3', 'scope3'],
            'CSRD': ['csrd', 'corporate sustainability reporting'],
            'ISSB': ['issb', 'ifrs s1', 'ifrs s2'],
            'TCFD': ['tcfd', 'task force'],
            'SB 253': ['sb 253', 'sb253'],
            'SB 261': ['sb 261', 'sb261'],
            'EEOC': ['eeoc', 'equal employment'],
            'Discrimination': ['discrimination', 'harassment'],
            'Pay Equity': ['pay equity', 'pay transparency'],
            'ADA': ['ada', 'americans with disabilities'],
            'Accessibility': ['accessibility', 'wcag']
        }
        
        for tag, keywords in tag_patterns.items():
            if any(kw in text for kw in keywords):
                tags.append(tag)
        
        return tags[:5]
    
    # ============================================================================
    # ENVIRONMENTAL MONITORING - OFFICIAL SOURCES ONLY
    # ============================================================================
    
    def check_sec_official(self):
        """Monitor SEC.gov official press releases"""
        print("Checking SEC official releases...")
        new_items = []
        
        feed_url = 'https://www.sec.gov/news/pressreleases.rss'
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:20]:
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                combined = f"{title} {description}".lower()
                
                # Only ESG/climate related official SEC actions
                is_esg = any(term in combined for term in [
                    'climate', 'esg', 'sustainability', 'greenhouse', 'emissions',
                    'disclosure', 'environmental'
                ])
                
                # Block personnel announcements and non-ESG fraud
                is_blocked = any(phrase in combined for phrase in [
                    'rejoin', 'to join', 'appointed', 'named to', 'deputy director',
                    'accounting fraud' if 'climate' not in combined and 'esg' not in combined else ''
                ])
                
                if is_esg and not is_blocked:
                    if not any(r['title'] == title for r in self.regulations):
                        pub_date = entry.get('published', entry.get('updated', ''))
                        parsed_date = self.parse_date(pub_date)
                        
                        if not self.is_recent_enough(parsed_date):
                            continue
                        
                        regulation = {
                            'id': len(self.regulations) + len(new_items) + 1,
                            'title': title,
                            'category': 'environmental',
                            'source_category': 'sec-official',
                            'jurisdiction': 'sec',
                            'type': self.categorize_type(title, description),
                            'priority': self.categorize_priority(title, description),
                            'date': parsed_date,
                            'isNew': True,
                            'description': description[:500] + ('...' if len(description) > 500 else ''),
                            'tags': self.extract_tags(title, description),
                            'effectiveDate': 'TBD',
                            'source_url': entry.get('link', ''),
                            'source_type': 'SEC Official'
                        }
                        new_items.append(regulation)
                        print(f"  Found: {title[:60]}...")
        
        except Exception as e:
            print(f"  Error parsing SEC feed: {e}")
        
        return new_items
    
    def check_federal_register(self):
        """Monitor Federal Register for ESG regulations and executive orders"""
        print("Checking Federal Register...")
        new_items = []
        
        # Federal Register RSS feeds
        feeds = [
            ('https://www.federalregister.gov/documents/search.rss?conditions%5Bagencies%5D%5B%5D=securities-and-exchange-commission&conditions%5Bterm%5D=climate', 'Federal Register - SEC Climate'),
            ('https://www.federalregister.gov/documents/search.rss?conditions%5Bagencies%5D%5B%5D=environmental-protection-agency&conditions%5Bterm%5D=climate', 'Federal Register - EPA Climate'),
        ]
        
        for feed_url, source_name in feeds:
            try:
                feed = feedparser.parse(feed_url)
                
                for entry in feed.entries[:10]:
                    title = entry.get('title', '')
                    description = entry.get('summary', entry.get('description', ''))
                    
                    if not any(r['title'] == title for r in self.regulations):
                        pub_date = entry.get('published', entry.get('updated', ''))
                        parsed_date = self.parse_date(pub_date)
                        
                        if not self.is_recent_enough(parsed_date):
                            continue
                        
                        combined = f"{title} {description}".lower()
                        
                        # Block state executive orders (only federal)
                        is_state_order = any(term in combined for term in [
                            'governor', 'state of california', 'state of new york',
                            'newsom', 'hochul', 'desantis'
                        ])
                        
                        if is_state_order:
                            continue
                        
                        # Determine if environmental or social
                        category = 'environmental'
                        if any(term in combined for term in ['dei', 'diversity', 'discrimination', 'equal employment']):
                            category = 'social'
                        
                        regulation = {
                            'id': len(self.regulations) + len(new_items) + 1,
                            'title': title,
                            'category': category,
                            'source_category': 'federal-register',
                            'jurisdiction': 'sec' if 'SEC' in source_name else 'federal',
                            'type': self.categorize_type(title, description),
                            'priority': self.categorize_priority(title, description),
                            'date': parsed_date,
                            'isNew': True,
                            'description': description[:500] + ('...' if len(description) > 500 else ''),
                            'tags': self.extract_tags(title, description),
                            'effectiveDate': 'TBD',
                            'source_url': entry.get('link', ''),
                            'source_type': source_name
                        }
                        new_items.append(regulation)
                        print(f"  Found: {title[:60]}...")
            
            except Exception as e:
                print(f"  Error parsing {source_name}: {e}")
        
        return new_items
    
    def check_eu_official(self):
        """Monitor EUR-Lex for official EU regulations"""
        print("Checking EUR-Lex official...")
        new_items = []
        
        feed_url = 'https://eur-lex.europa.eu/EN/display-feed.do?do-feed=allnew'
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:30]:
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                combined = f"{title} {description}".lower()
                
                # Only ESG/sustainability related
                is_esg = any(term in combined for term in [
                    'csrd', 'esrs', 'sustainability', 'climate', 'taxonomy',
                    'environmental', 'disclosure', 'esg'
                ])
                
                if is_esg:
                    if not any(r['title'] == title for r in self.regulations):
                        pub_date = entry.get('published', entry.get('updated', ''))
                        parsed_date = self.parse_date(pub_date)
                        
                        if not self.is_recent_enough(parsed_date):
                            continue
                        
                        regulation = {
                            'id': len(self.regulations) + len(new_items) + 1,
                            'title': title,
                            'category': 'environmental',
                            'source_category': 'eu-official',
                            'jurisdiction': 'eu',
                            'type': self.categorize_type(title, description),
                            'priority': self.categorize_priority(title, description),
                            'date': parsed_date,
                            'isNew': True,
                            'description': description[:500] + ('...' if len(description) > 500 else ''),
                            'tags': self.extract_tags(title, description),
                            'effectiveDate': 'TBD',
                            'source_url': entry.get('link', ''),
                            'source_type': 'EUR-Lex Official'
                        }
                        new_items.append(regulation)
                        print(f"  Found: {title[:60]}...")
        
        except Exception as e:
            print(f"  Error parsing EUR-Lex: {e}")
        
        return new_items
    
    def check_carb_official(self):
        """Monitor California Air Resources Board (official)"""
        print("Checking CARB official...")
        new_items = []
        
        feed_url = 'https://ww2.arb.ca.gov/rss.xml'
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:15]:
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                combined = f"{title} {description}".lower()
                
                # SB 253, SB 261, or climate related
                is_relevant = any(term in combined for term in [
                    'sb 253', 'sb253', 'sb 261', 'sb261',
                    'climate disclosure', 'greenhouse gas', 'emissions'
                ])
                
                if is_relevant:
                    if not any(r['title'] == title for r in self.regulations):
                        pub_date = entry.get('published', entry.get('updated', ''))
                        parsed_date = self.parse_date(pub_date)
                        
                        if not self.is_recent_enough(parsed_date):
                            continue
                        
                        regulation = {
                            'id': len(self.regulations) + len(new_items) + 1,
                            'title': title,
                            'category': 'environmental',
                            'source_category': 'california-official',
                            'jurisdiction': 'california',
                            'type': self.categorize_type(title, description),
                            'priority': self.categorize_priority(title, description),
                            'date': parsed_date,
                            'isNew': True,
                            'description': description[:500] + ('...' if len(description) > 500 else ''),
                            'tags': self.extract_tags(title, description) + ['California'],
                            'effectiveDate': 'TBD',
                            'source_url': entry.get('link', ''),
                            'source_type': 'CARB Official'
                        }
                        new_items.append(regulation)
                        print(f"  Found: {title[:60]}...")
        
        except Exception as e:
            print(f"  Error parsing CARB: {e}")
        
        return new_items
    
    def check_issb_official(self):
        """Monitor IFRS/ISSB official"""
        print("Checking IFRS/ISSB official...")
        new_items = []
        
        feed_url = 'https://www.ifrs.org/news-and-events/news.xml'
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:10]:
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                combined = f"{title} {description}".lower()
                
                # ISSB/sustainability related
                is_relevant = any(term in combined for term in [
                    'issb', 'ifrs s1', 'ifrs s2', 'sustainability', 'climate'
                ])
                
                if is_relevant:
                    if not any(r['title'] == title for r in self.regulations):
                        pub_date = entry.get('published', entry.get('updated', ''))
                        parsed_date = self.parse_date(pub_date)
                        
                        if not self.is_recent_enough(parsed_date):
                            continue
                        
                        regulation = {
                            'id': len(self.regulations) + len(new_items) + 1,
                            'title': title,
                            'category': 'environmental',
                            'source_category': 'issb-official',
                            'jurisdiction': 'international',
                            'type': self.categorize_type(title, description),
                            'priority': self.categorize_priority(title, description),
                            'date': parsed_date,
                            'isNew': True,
                            'description': description[:500] + ('...' if len(description) > 500 else ''),
                            'tags': self.extract_tags(title, description),
                            'effectiveDate': 'TBD',
                            'source_url': entry.get('link', ''),
                            'source_type': 'IFRS/ISSB Official'
                        }
                        new_items.append(regulation)
                        print(f"  Found: {title[:60]}...")
        
        except Exception as e:
            print(f"  Error parsing ISSB: {e}")
        
        return new_items
    
    def check_fca_official(self):
        """Monitor UK FCA official"""
        print("Checking FCA official...")
        new_items = []
        
        feed_url = 'https://www.fca.org.uk/news/news.rss'
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:15]:
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                combined = f"{title} {description}".lower()
                
                # SDR/sustainability related
                is_relevant = any(term in combined for term in [
                    'sdr', 'sustainability', 'disclosure', 'esg', 'climate'
                ])
                
                if is_relevant:
                    if not any(r['title'] == title for r in self.regulations):
                        pub_date = entry.get('published', entry.get('updated', ''))
                        parsed_date = self.parse_date(pub_date)
                        
                        if not self.is_recent_enough(parsed_date):
                            continue
                        
                        regulation = {
                            'id': len(self.regulations) + len(new_items) + 1,
                            'title': title,
                            'category': 'environmental',
                            'source_category': 'uk-official',
                            'jurisdiction': 'uk',
                            'type': self.categorize_type(title, description),
                            'priority': self.categorize_priority(title, description),
                            'date': parsed_date,
                            'isNew': True,
                            'description': description[:500] + ('...' if len(description) > 500 else ''),
                            'tags': self.extract_tags(title, description),
                            'effectiveDate': 'TBD',
                            'source_url': entry.get('link', ''),
                            'source_type': 'FCA Official'
                        }
                        new_items.append(regulation)
                        print(f"  Found: {title[:60]}...")
        
        except Exception as e:
            print(f"  Error parsing FCA: {e}")
        
        return new_items
    
    def check_canada_official(self):
        """Monitor Canadian securities regulators official"""
        print("Checking Canada OSC official...")
        new_items = []
        
        feed_url = 'https://www.osc.ca/en/news-events/news.rss'
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:15]:
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                combined = f"{title} {description}".lower()
                
                # Climate/ESG related
                is_relevant = any(term in combined for term in [
                    'climate', 'esg', 'sustainability', 'disclosure', 'environmental'
                ])
                
                if is_relevant:
                    if not any(r['title'] == title for r in self.regulations):
                        pub_date = entry.get('published', entry.get('updated', ''))
                        parsed_date = self.parse_date(pub_date)
                        
                        if not self.is_recent_enough(parsed_date):
                            continue
                        
                        regulation = {
                            'id': len(self.regulations) + len(new_items) + 1,
                            'title': title,
                            'category': 'environmental',
                            'source_category': 'canada-official',
                            'jurisdiction': 'canada',
                            'type': self.categorize_type(title, description),
                            'priority': self.categorize_priority(title, description),
                            'date': parsed_date,
                            'isNew': True,
                            'description': description[:500] + ('...' if len(description) > 500 else ''),
                            'tags': self.extract_tags(title, description),
                            'effectiveDate': 'TBD',
                            'source_url': entry.get('link', ''),
                            'source_type': 'OSC Official'
                        }
                        new_items.append(regulation)
                        print(f"  Found: {title[:60]}...")
        
        except Exception as e:
            print(f"  Error parsing OSC: {e}")
        
        return new_items
    
    # ============================================================================
    # SOCIAL MONITORING - OFFICIAL SOURCES + REUTERS LEGAL
    # ============================================================================
    
    def check_eeoc_official(self):
        """Monitor EEOC official"""
        print("Checking EEOC official...")
        new_items = []
        
        feed_url = 'https://www.eeoc.gov/rss/eeoc.xml'
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:20]:
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                combined = f"{title} {description}".lower()
                
                # DEI/discrimination related
                is_relevant = any(term in combined for term in [
                    'discrimination', 'harassment', 'lawsuit', 'settlement',
                    'equal employment', 'title vii', 'pay equity'
                ])
                
                if is_relevant:
                    if not any(r['title'] == title for r in self.regulations):
                        pub_date = entry.get('published', entry.get('updated', ''))
                        parsed_date = self.parse_date(pub_date)
                        
                        if not self.is_recent_enough(parsed_date):
                            continue
                        
                        regulation = {
                            'id': len(self.regulations) + len(new_items) + 1,
                            'title': title,
                            'category': 'social',
                            'source_category': 'eeoc-official',
                            'jurisdiction': 'eeoc',
                            'type': 'enforcement',
                            'priority': self.categorize_priority(title, description),
                            'date': parsed_date,
                            'isNew': True,
                            'description': description[:500] + ('...' if len(description) > 500 else ''),
                            'tags': self.extract_tags(title, description),
                            'effectiveDate': 'TBD',
                            'source_url': entry.get('link', ''),
                            'source_type': 'EEOC Official'
                        }
                        new_items.append(regulation)
                        print(f"  Found: {title[:60]}...")
        
        except Exception as e:
            print(f"  Error parsing EEOC: {e}")
        
        return new_items
    
    def check_fcc_official(self):
        """Monitor FCC official"""
        print("Checking FCC official...")
        new_items = []
        
        feed_url = 'https://www.fcc.gov/news-events/rss/allnews.rss'
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:20]:
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                combined = f"{title} {description}".lower()
                
                # Diversity/DEI/policy related
                is_relevant = any(term in combined for term in [
                    'diversity', 'inclusion', 'equal employment', 'dei',
                    'chairman letter', 'policy statement', 'diversity equity',
                    'eeo', 'equal opportunity'
                ])
                
                if is_relevant:
                    if not any(r['title'] == title for r in self.regulations):
                        pub_date = entry.get('published', entry.get('updated', ''))
                        parsed_date = self.parse_date(pub_date)
                        
                        if not self.is_recent_enough(parsed_date):
                            continue
                        
                        regulation = {
                            'id': len(self.regulations) + len(new_items) + 1,
                            'title': title,
                            'category': 'social',
                            'source_category': 'fcc-official',
                            'jurisdiction': 'fcc',
                            'type': self.categorize_type(title, description),
                            'priority': self.categorize_priority(title, description),
                            'date': parsed_date,
                            'isNew': True,
                            'description': description[:500] + ('...' if len(description) > 500 else ''),
                            'tags': self.extract_tags(title, description),
                            'effectiveDate': 'TBD',
                            'source_url': entry.get('link', ''),
                            'source_type': 'FCC Official'
                        }
                        new_items.append(regulation)
                        print(f"  Found: {title[:60]}...")
        
        except Exception as e:
            print(f"  Error parsing FCC: {e}")
        
        return new_items
    
    def check_wcag_official(self):
        """Monitor W3C WAI official for WCAG updates"""
        print("Checking W3C WCAG official...")
        new_items = []
        
        feed_url = 'https://www.w3.org/WAI/feed.xml'
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:10]:
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                combined = f"{title} {description}".lower()
                
                # WCAG/accessibility standards
                is_relevant = any(term in combined for term in [
                    'wcag', 'guideline', 'standard', 'accessibility'
                ])
                
                if is_relevant:
                    if not any(r['title'] == title for r in self.regulations):
                        pub_date = entry.get('published', entry.get('updated', ''))
                        parsed_date = self.parse_date(pub_date)
                        
                        if not self.is_recent_enough(parsed_date):
                            continue
                        
                        regulation = {
                            'id': len(self.regulations) + len(new_items) + 1,
                            'title': title,
                            'category': 'social',
                            'source_category': 'accessibility-standards',
                            'jurisdiction': 'wcag',
                            'type': 'reporting',
                            'priority': 'high' if 'wcag' in combined and any(v in combined for v in ['2.', '3.']) else 'medium',
                            'date': parsed_date,
                            'isNew': True,
                            'description': description[:500] + ('...' if len(description) > 500 else ''),
                            'tags': self.extract_tags(title, description),
                            'effectiveDate': 'TBD',
                            'source_url': entry.get('link', ''),
                            'source_type': 'W3C WAI Official'
                        }
                        new_items.append(regulation)
                        print(f"  Found: {title[:60]}...")
        
        except Exception as e:
            print(f"  Error parsing W3C: {e}")
        
        return new_items
    
    def check_targeted_news(self):
        """Monitor targeted news searches for items missed by official feeds"""
        print("Checking targeted news searches...")
        new_items = []
        
        # Very specific searches for regulatory gaps
        targeted_searches = [
            ('https://news.google.com/rss/search?q="FCC+Chairman"+AND+DEI+OR+diversity&hl=en-US&gl=US&ceid=US:en', 'FCC Chairman DEI Policy'),
            ('https://news.google.com/rss/search?q=EEOC+AND+("files+lawsuit"+OR+settlement+OR+investigation)&hl=en-US&gl=US&ceid=US:en', 'EEOC Enforcement'),
            ('https://news.google.com/rss/search?q=Trump+AND+"executive+order"+AND+(climate+OR+DEI)&hl=en-US&gl=US&ceid=US:en', 'Trump Executive Orders'),
        ]
        
        for feed_url, source_name in targeted_searches:
            try:
                feed = feedparser.parse(feed_url)
                
                for entry in feed.entries[:10]:  # Only top 10 most relevant
                    title = entry.get('title', '')
                    description = entry.get('summary', entry.get('description', ''))
                    combined = f"{title} {description}".lower()
                    
                    # STRICT: Block all commentary/how-to content
                    is_blocked = any(phrase in combined for phrase in [
                        'what employers should know', 'what companies should know',
                        'what employers need to know', 'what businesses should know',
                        'guide to', 'how to', 'prepare for', 'countdown to',
                        'day 1' if 'governor' in combined or 'state' in combined else '',  # Block state gov Day 1
                        'laboremploymentlawblog', 'sheppard mullin', 'baker donelson'
                    ])
                    
                    # Must be actual regulatory action
                    has_action = any(term in combined for term in [
                        'files lawsuit', 'lawsuit filed', 'settlement', 'executive order',
                        'chairman letter', 'policy statement', 'fcc announces',
                        'eeoc files', 'investigation', 'sues', 'sued'
                    ])
                    
                    if has_action and not is_blocked:
                        # Additional filter: Skip random local lawsuits (not EEOC/federal)
                        is_local_lawsuit = (
                            'lawsuit' in combined and 
                            'eeoc' not in combined and 
                            'sec' not in combined and
                            'fcc' not in combined and
                            'doj' not in combined
                        )
                        
                        if is_local_lawsuit:
                            continue
                        
                        if not any(r['title'] == title for r in self.regulations):
                            pub_date = entry.get('published', entry.get('updated', ''))
                            parsed_date = self.parse_date(pub_date)
                            
                            if not self.is_recent_enough(parsed_date):
                                continue
                            
                            # Determine category
                            category = 'social'
                            if 'climate' in combined or 'emissions' in combined or 'esg' in combined:
                                category = 'environmental'
                            
                            # Determine source_category
                            source_category = 'news-enforcement'
                            if 'eeoc' in combined:
                                source_category = 'eeoc-official'  # Will show under EEOC tab
                            elif 'fcc' in combined:
                                source_category = 'fcc-official'  # Will show under FCC tab
                            elif 'executive order' in combined:
                                source_category = 'executive-order'
                            
                            regulation = {
                                'id': len(self.regulations) + len(new_items) + 1,
                                'title': title,
                                'category': category,
                                'source_category': source_category,
                                'jurisdiction': 'federal',
                                'type': 'enforcement',
                                'priority': 'high',
                                'date': parsed_date,
                                'isNew': True,
                                'description': description[:500] + ('...' if len(description) > 500 else ''),
                                'tags': self.extract_tags(title, description) + ['News'],
                                'effectiveDate': 'TBD',
                                'source_url': entry.get('link', ''),
                                'source_type': source_name
                            }
                            new_items.append(regulation)
                            print(f"  Found: {title[:60]}...")
            
            except Exception as e:
                print(f"  Error parsing {source_name}: {e}")
        
        return new_items
    
    def check_reuters_legal(self):
        """Monitor Reuters Legal for federal enforcement only - VERY STRICT"""
        print("Checking Reuters Legal (federal enforcement only)...")
        new_items = []
        
        feed_url = 'https://www.reuters.com/rssfeed/legal'
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:20]:
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                combined = f"{title} {description}".lower()
                
                # MUST mention a federal agency
                has_federal_agency = any(agency in combined for agency in [
                    'eeoc', 'sec', 'fcc', 'doj', 'epa', 'federal trade commission',
                    'justice department', 'securities and exchange'
                ])
                
                # MUST have ESG/DEI keywords
                has_esg = any(term in combined for term in [
                    'climate', 'esg', 'sustainability', 'emissions',
                    'discrimination', 'dei', 'diversity', 'accessibility', 'ada',
                    'pay equity', 'board diversity', 'csrd', 'sb 253', 'sb 261'
                ])
                
                # MUST have enforcement action
                has_enforcement = any(term in combined for term in [
                    'lawsuit', 'sues', 'sued', 'files lawsuit', 'settlement',
                    'court', 'ruling', 'injunction', 'blocks', 'executive order',
                    'consent decree', 'charges', 'investigation'
                ])
                
                # BLOCK commentary/personnel/fraud (unless ESG fraud)
                is_blocked = any(phrase in combined for phrase in [
                    'what employers should know', 'what companies should know',
                    'guide to', 'how to', 'prepare for',
                    'rejoin', 'to join', 'appointed', 'named to',
                    'accounting fraud' if 'climate' not in combined and 'esg' not in combined else ''
                ])
                
                if has_federal_agency and has_esg and has_enforcement and not is_blocked:
                    if not any(r['title'] == title for r in self.regulations):
                        pub_date = entry.get('published', entry.get('updated', ''))
                        parsed_date = self.parse_date(pub_date)
                        
                        if not self.is_recent_enough(parsed_date):
                            continue
                        
                        # Determine category
                        category = 'environmental'
                        if any(term in combined for term in ['eeoc', 'discrimination', 'dei', 'diversity', 'ada', 'accessibility', 'pay equity']):
                            category = 'social'
                        
                        # Determine source_category for proper tab routing
                        source_category = 'reuters-enforcement'
                        if 'eeoc' in combined:
                            source_category = 'eeoc-official'
                        elif 'fcc' in combined:
                            source_category = 'fcc-official'
                        
                        regulation = {
                            'id': len(self.regulations) + len(new_items) + 1,
                            'title': title,
                            'category': category,
                            'source_category': source_category,
                            'jurisdiction': 'federal',
                            'type': 'enforcement',
                            'priority': 'high',
                            'date': parsed_date,
                            'isNew': True,
                            'description': description[:500] + ('...' if len(description) > 500 else ''),
                            'tags': self.extract_tags(title, description) + ['Reuters'],
                            'effectiveDate': 'TBD',
                            'source_url': entry.get('link', ''),
                            'source_type': 'Reuters Legal'
                        }
                        new_items.append(regulation)
                        print(f"  Found: {title[:60]}...")
        
        except Exception as e:
            print(f"  Error parsing Reuters Legal: {e}")
        
        return new_items
        
        except Exception as e:
            print(f"  Error parsing Reuters Legal: {e}")
        
        return new_items
    
    # ============================================================================
    # DASHBOARD UPDATE
    # ============================================================================
    
    def update_dashboard(self):
        """Update the HTML dashboard with current regulations data"""
        print("Updating dashboard...")
        
        if not self.dashboard_file.exists():
            print("  Dashboard file not found, skipping update")
            return
        
        try:
            with open(self.dashboard_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Convert regulations to JavaScript format
            js_data = json.dumps(self.regulations, indent=12)
            
            # Find and replace the regulations array
            start_marker = "const regulations = ["
            end_marker = "];"
            
            start_idx = html_content.find(start_marker)
            if start_idx == -1:
                print("  ERROR: Could not find regulations array")
                return
            
            # Find the closing ]
            end_idx = html_content.find(end_marker, start_idx)
            if end_idx == -1:
                print("  ERROR: Could not find closing bracket")
                return
            
            # Replace the content between the markers
            new_content = (
                html_content[:start_idx + len(start_marker)] +
                "\n" + js_data + "\n        " +
                html_content[end_idx:]
            )
            
            with open(self.dashboard_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print(f"  Dashboard updated with {len(self.regulations)} regulations")
        
        except Exception as e:
            print(f"  Error updating dashboard: {e}")
    
    # ============================================================================
    # EMAIL ALERTS
    # ============================================================================
    
    def send_email_alert(self, new_regulations):
        """Send email alert for new regulations - ONLY ON MONDAYS (weekly digest)"""
        if not EMAIL_PASSWORD or EMAIL_PASSWORD == 'your-app-password':
            print("Skipping email (email not configured)")
            return
        
        # Check if today is Monday (0 = Monday, 6 = Sunday)
        is_monday = datetime.now().weekday() == 0
        
        if not is_monday:
            print(f"Skipping email (not Monday - will send weekly digest on Monday)")
            return
        
        # Get all regulations marked as "new" from the past week
        one_week_ago = datetime.now() - timedelta(days=7)
        weekly_new_regs = [
            r for r in self.regulations 
            if r.get('isNew') and datetime.strptime(r['date'], '%Y-%m-%d') >= one_week_ago
        ]
        
        if not weekly_new_regs:
            print("Skipping email (no new regulations this week)")
            return
        
        try:
            # Group by category
            env_regs = [r for r in weekly_new_regs if r.get('category') == 'environmental']
            social_regs = [r for r in weekly_new_regs if r.get('category') == 'social']
            
            # Create HTML email
            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>📅 Weekly ESG Regulations Digest</h2>
                <p><strong>{len(weekly_new_regs)} new regulations this week</strong></p>
                
                <h3>🌿 Environmental ({len(env_regs)})</h3>
                <ul>
                {''.join([f'<li><strong>{r["title"]}</strong><br>Source: {r["source_type"]}<br><a href="{r["source_url"]}">View Details</a></li>' for r in env_regs[:10]])}
                </ul>
                
                <h3>👥 Social ({len(social_regs)})</h3>
                <ul>
                {''.join([f'<li><strong>{r["title"]}</strong><br>Source: {r["source_type"]}<br><a href="{r["source_url"]}">View Details</a></li>' for r in social_regs[:10]])}
                </ul>
                
                <p><a href="https://isabelfields.github.io/esg-regulations-monitor/esg-regulations-monitor.html">View Full Dashboard</a></p>
            </body>
            </html>
            """
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f'📅 Weekly ESG Digest: {len(weekly_new_regs)} New Regulations'
            msg['From'] = EMAIL_FROM
            msg['To'] = EMAIL_TO
            
            msg.attach(MIMEText(html_body, 'html'))
            
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(EMAIL_FROM, EMAIL_PASSWORD)
                server.send_message(msg)
            
            print(f"✅ Email sent to {EMAIL_TO}")
        
        except Exception as e:
            print(f"Error sending email: {e}")
    
    # ============================================================================
    # MAIN RUN
    # ============================================================================
    
    def run(self):
        """Main monitoring loop"""
        print(f"\n{'='*70}")
        print(f"ESG Regulations Monitor - Official Sources Only")
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")
        
        new_regulations = []
        
        print("=" * 70)
        print("ENVIRONMENTAL (Official Sources)")
        print("=" * 70)
        
        new_regulations.extend(self.check_sec_official())
        new_regulations.extend(self.check_federal_register())
        new_regulations.extend(self.check_eu_official())
        new_regulations.extend(self.check_carb_official())
        new_regulations.extend(self.check_issb_official())
        new_regulations.extend(self.check_fca_official())
        new_regulations.extend(self.check_canada_official())
        
        print("\n" + "=" * 70)
        print("SOCIAL (Official + Reuters Legal)")
        print("=" * 70)
        
        new_regulations.extend(self.check_eeoc_official())
        new_regulations.extend(self.check_fcc_official())
        new_regulations.extend(self.check_wcag_official())
        new_regulations.extend(self.check_reuters_legal())
        
        # Mark old regs as not new
        for reg in self.regulations:
            reg['isNew'] = False
        
        # Add new regulations
        print("\n" + "=" * 70)
        if new_regulations:
            print(f"✅ Found {len(new_regulations)} new regulation(s)")
            
            env_count = len([r for r in new_regulations if r.get('category') == 'environmental'])
            social_count = len([r for r in new_regulations if r.get('category') == 'social'])
            
            print(f"   Environmental: {env_count}")
            print(f"   Social: {social_count}")
            
            self.regulations.extend(new_regulations)
            self.save_regulations()
            # Dashboard now loads from regulations.json directly - no need to update HTML
            # Email only sent on Mondays (weekly digest of all new regulations)
            self.send_email_alert(new_regulations)
        else:
            print("✅ No new regulations found")
        
        print(f"\nTotal regulations tracked: {len(self.regulations)}")
        print(f"{'='*70}\n")

if __name__ == '__main__':
    monitor = ESGMonitor()
    monitor.run()
