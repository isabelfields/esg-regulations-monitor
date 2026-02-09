#!/usr/bin/env python3
"""
ESG Regulations Monitor - Final Clean Version
Environmental: Official sources + Reuters Legal (climate lawsuits)
Social: Official sources + Reuters Legal (EEOC/FCC/ADA enforcement)
"""

import feedparser
import json
import smtplib
import os
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

# Email configuration
EMAIL_FROM = os.environ.get('EMAIL_FROM', '')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', '')
EMAIL_TO = os.environ.get('EMAIL_TO', '')

class ESGMonitor:
    def __init__(self):
        self.regulations_file = Path('regulations.json')
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
            print(f"Saved {len(self.regulations)} regulations")
        except Exception as e:
            print(f"Error saving: {e}")
    
    def parse_date(self, date_str):
        """Parse date to YYYY-MM-DD"""
        if not date_str:
            return datetime.now().strftime('%Y-%m-%d')
        
        try:
            for fmt in ['%a, %d %b %Y %H:%M:%S %Z', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%d']:
                try:
                    dt = datetime.strptime(date_str.split('.')[0].split('+')[0].strip(), fmt)
                    return dt.strftime('%Y-%m-%d')
                except:
                    continue
            return datetime.now().strftime('%Y-%m-%d')
        except:
            return datetime.now().strftime('%Y-%m-%d')
    
    def is_recent_enough(self, date_string):
        """Check if from Jan 1, 2025 or later"""
        try:
            reg_date = datetime.strptime(date_string, '%Y-%m-%d')
            return reg_date >= datetime(2025, 1, 1)
        except:
            return True
    
    def categorize_priority(self, title, description):
        """Determine priority level"""
        text = f"{title} {description}".lower()
        
        if any(w in text for w in ['final rule', 'adopted', 'enacted', 'injunction', 'lawsuit', 'court order']):
            return 'critical'
        elif any(w in text for w in ['proposed', 'draft', 'consultation']):
            return 'high'
        return 'medium'
    
    def categorize_type(self, title, description):
        """Categorize type"""
        text = f"{title} {description}".lower()
        
        if 'disclosure' in text or 'reporting' in text:
            return 'disclosure'
        elif 'enforcement' in text or 'lawsuit' in text:
            return 'enforcement'
        return 'reporting'
    
    def extract_tags(self, title, description):
        """Extract tags"""
        text = f"{title} {description}".lower()
        tags = []
        
        tag_map = {
            'Climate': ['climate', 'ghg', 'emissions'],
            'CSRD': ['csrd'],
            'ISSB': ['issb', 'ifrs'],
            'SB 253': ['sb 253', 'sb253'],
            'SB 261': ['sb 261', 'sb261'],
            'EEOC': ['eeoc'],
            'Discrimination': ['discrimination'],
            'ADA': ['ada']
        }
        
        for tag, keywords in tag_map.items():
            if any(kw in text for kw in keywords):
                tags.append(tag)
        
        return tags[:5]
    
    # ========================================================================
    # ENVIRONMENTAL - OFFICIAL SOURCES
    # ========================================================================
    
    def check_sec_official(self):
        """SEC official press releases"""
        print("Checking SEC official...")
        new_items = []
        
        try:
            feed = feedparser.parse('https://www.sec.gov/news/pressreleases.rss')
            
            for entry in feed.entries[:20]:
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                combined = f"{title} {description}".lower()
                
                # Only climate/ESG related
                if any(term in combined for term in ['climate', 'esg', 'sustainability', 'greenhouse', 'emissions', 'disclosure']):
                    if not any(r['title'] == title for r in self.regulations):
                        pub_date = entry.get('published', entry.get('updated', ''))
                        parsed_date = self.parse_date(pub_date)
                        
                        if not self.is_recent_enough(parsed_date):
                            continue
                        
                        new_items.append({
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
                        })
                        print(f"  Found: {title[:60]}...")
        except Exception as e:
            print(f"  Error: {e}")
        
        return new_items
    
    def check_federal_register(self):
        """Federal Register official"""
        print("Checking Federal Register...")
        new_items = []
        
        feeds = [
            ('https://www.federalregister.gov/documents/search.rss?conditions%5Bagencies%5D%5B%5D=securities-and-exchange-commission&conditions%5Bterm%5D=climate', 'Federal Register - SEC'),
            ('https://www.federalregister.gov/documents/search.rss?conditions%5Bagencies%5D%5B%5D=environmental-protection-agency&conditions%5Bterm%5D=climate', 'Federal Register - EPA'),
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
                        
                        new_items.append({
                            'id': len(self.regulations) + len(new_items) + 1,
                            'title': title,
                            'category': 'environmental',
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
                        })
                        print(f"  Found: {title[:60]}...")
            except Exception as e:
                print(f"  Error {source_name}: {e}")
        
        return new_items
    
    def check_eu_official(self):
        """EUR-Lex official"""
        print("Checking EUR-Lex...")
        new_items = []
        
        try:
            feed = feedparser.parse('https://eur-lex.europa.eu/EN/display-feed.do?do-feed=allnew')
            
            for entry in feed.entries[:30]:
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                combined = f"{title} {description}".lower()
                
                if any(term in combined for term in ['csrd', 'esrs', 'sustainability', 'climate', 'taxonomy', 'esg']):
                    if not any(r['title'] == title for r in self.regulations):
                        pub_date = entry.get('published', entry.get('updated', ''))
                        parsed_date = self.parse_date(pub_date)
                        
                        if not self.is_recent_enough(parsed_date):
                            continue
                        
                        new_items.append({
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
                        })
                        print(f"  Found: {title[:60]}...")
        except Exception as e:
            print(f"  Error: {e}")
        
        return new_items
    
    def check_issb_official(self):
        """IFRS/ISSB official"""
        print("Checking IFRS/ISSB...")
        new_items = []
        
        try:
            feed = feedparser.parse('https://www.ifrs.org/news-and-events/news.xml')
            
            for entry in feed.entries[:10]:
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                combined = f"{title} {description}".lower()
                
                if any(term in combined for term in ['issb', 'ifrs s1', 'ifrs s2', 'sustainability', 'climate']):
                    if not any(r['title'] == title for r in self.regulations):
                        pub_date = entry.get('published', entry.get('updated', ''))
                        parsed_date = self.parse_date(pub_date)
                        
                        if not self.is_recent_enough(parsed_date):
                            continue
                        
                        new_items.append({
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
                        })
                        print(f"  Found: {title[:60]}...")
        except Exception as e:
            print(f"  Error: {e}")
        
        return new_items
    
    def check_fca_official(self):
        """UK FCA official"""
        print("Checking FCA...")
        new_items = []
        
        try:
            feed = feedparser.parse('https://www.fca.org.uk/news/news.rss')
            
            for entry in feed.entries[:15]:
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                combined = f"{title} {description}".lower()
                
                if any(term in combined for term in ['sdr', 'sustainability', 'disclosure', 'esg', 'climate']):
                    if not any(r['title'] == title for r in self.regulations):
                        pub_date = entry.get('published', entry.get('updated', ''))
                        parsed_date = self.parse_date(pub_date)
                        
                        if not self.is_recent_enough(parsed_date):
                            continue
                        
                        new_items.append({
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
                        })
                        print(f"  Found: {title[:60]}...")
        except Exception as e:
            print(f"  Error: {e}")
        
        return new_items
    
    def check_canada_official(self):
        """Canada OSC official"""
        print("Checking Canada OSC...")
        new_items = []
        
        try:
            feed = feedparser.parse('https://www.osc.ca/en/news-events/news.rss')
            
            for entry in feed.entries[:15]:
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                combined = f"{title} {description}".lower()
                
                if any(term in combined for term in ['climate', 'esg', 'sustainability', 'disclosure']):
                    if not any(r['title'] == title for r in self.regulations):
                        pub_date = entry.get('published', entry.get('updated', ''))
                        parsed_date = self.parse_date(pub_date)
                        
                        if not self.is_recent_enough(parsed_date):
                            continue
                        
                        new_items.append({
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
                        })
                        print(f"  Found: {title[:60]}...")
        except Exception as e:
            print(f"  Error: {e}")
        
        return new_items
    
    def check_reuters_environmental(self):
        """Reuters Legal - Environmental only (climate lawsuits, SB 253 injunction)"""
        print("Checking Reuters Legal (Environmental)...")
        new_items = []
        
        try:
            feed = feedparser.parse('https://www.reuters.com/rssfeed/legal')
            
            for entry in feed.entries[:20]:
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                combined = f"{title} {description}".lower()
                
                # Must have environmental/climate keywords
                has_climate = any(term in combined for term in [
                    'climate', 'esg', 'sustainability', 'greenhouse', 'emissions',
                    'sb 253', 'sb 261', 'csrd', 'greenwashing'
                ])
                
                # Must have enforcement keywords
                has_enforcement = any(term in combined for term in [
                    'lawsuit', 'sues', 'sued', 'court', 'judge', 'injunction',
                    'blocks', 'ruling', 'settlement'
                ])
                
                # Block commentary
                is_junk = any(phrase in combined for phrase in [
                    'what companies should know', 'what employers should know',
                    'guide to', 'how to', 'countdown to'
                ])
                
                if has_climate and has_enforcement and not is_junk:
                    if not any(r['title'] == title for r in self.regulations):
                        pub_date = entry.get('published', entry.get('updated', ''))
                        parsed_date = self.parse_date(pub_date)
                        
                        if not self.is_recent_enough(parsed_date):
                            continue
                        
                        new_items.append({
                            'id': len(self.regulations) + len(new_items) + 1,
                            'title': title,
                            'category': 'environmental',
                            'source_category': 'reuters-enforcement',
                            'jurisdiction': 'california' if 'sb 2' in combined else 'international',
                            'type': 'enforcement',
                            'priority': 'critical',
                            'date': parsed_date,
                            'isNew': True,
                            'description': description[:500] + ('...' if len(description) > 500 else ''),
                            'tags': self.extract_tags(title, description) + ['Reuters'],
                            'effectiveDate': 'TBD',
                            'source_url': entry.get('link', ''),
                            'source_type': 'Reuters Legal'
                        })
                        print(f"  Found: {title[:60]}...")
        except Exception as e:
            print(f"  Error: {e}")
        
        return new_items
    
    # ========================================================================
    # SOCIAL - OFFICIAL SOURCES + REUTERS
    # ========================================================================
    
    def check_eeoc_official(self):
        """EEOC official"""
        print("Checking EEOC official...")
        new_items = []
        
        try:
            feed = feedparser.parse('https://www.eeoc.gov/rss/eeoc.xml')
            
            for entry in feed.entries[:20]:
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                
                if not any(r['title'] == title for r in self.regulations):
                    pub_date = entry.get('published', entry.get('updated', ''))
                    parsed_date = self.parse_date(pub_date)
                    
                    if not self.is_recent_enough(parsed_date):
                        continue
                    
                    new_items.append({
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
                    })
                    print(f"  Found: {title[:60]}...")
        except Exception as e:
            print(f"  Error: {e}")
        
        return new_items
    
    def check_fcc_official(self):
        """FCC official"""
        print("Checking FCC official...")
        new_items = []
        
        try:
            feed = feedparser.parse('https://www.fcc.gov/news-events/rss/allnews.rss')
            
            for entry in feed.entries[:20]:
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                combined = f"{title} {description}".lower()
                
                # Only diversity/DEI related
                if any(term in combined for term in ['diversity', 'inclusion', 'equal employment', 'dei']):
                    if not any(r['title'] == title for r in self.regulations):
                        pub_date = entry.get('published', entry.get('updated', ''))
                        parsed_date = self.parse_date(pub_date)
                        
                        if not self.is_recent_enough(parsed_date):
                            continue
                        
                        new_items.append({
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
                        })
                        print(f"  Found: {title[:60]}...")
        except Exception as e:
            print(f"  Error: {e}")
        
        return new_items
    
    def check_reuters_social(self):
        """Reuters Legal - Social only (EEOC, FCC, ADA enforcement)"""
        print("Checking Reuters Legal (Social)...")
        new_items = []
        
        try:
            feed = feedparser.parse('https://www.reuters.com/rssfeed/legal')
            
            for entry in feed.entries[:20]:
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                combined = f"{title} {description}".lower()
                
                # Must have social/DEI keywords
                has_social = any(term in combined for term in [
                    'eeoc', 'discrimination', 'diversity', 'ada', 'accessibility',
                    'pay equity', 'harassment', 'fcc', 'equal employment'
                ])
                
                # Must have enforcement keywords
                has_enforcement = any(term in combined for term in [
                    'lawsuit', 'sues', 'sued', 'investigation', 'investigates',
                    'settlement', 'court', 'judge', 'ruling', 'files lawsuit',
                    'eeoc files', 'fcc probes', 'consent decree'
                ])
                
                # Block commentary/junk
                is_junk = any(phrase in combined for phrase in [
                    'what employers should know', 'what companies should know',
                    'guide to', 'how to', 'countdown to', 'day 1',
                    'laboremploymentlawblog', 'sheppard, mullin'
                ])
                
                if has_social and has_enforcement and not is_junk:
                    if not any(r['title'] == title for r in self.regulations):
                        pub_date = entry.get('published', entry.get('updated', ''))
                        parsed_date = self.parse_date(pub_date)
                        
                        if not self.is_recent_enough(parsed_date):
                            continue
                        
                        new_items.append({
                            'id': len(self.regulations) + len(new_items) + 1,
                            'title': title,
                            'category': 'social',
                            'source_category': 'reuters-enforcement',
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
                        })
                        print(f"  Found: {title[:60]}...")
        except Exception as e:
            print(f"  Error: {e}")
        
        return new_items
    
    # ========================================================================
    # EMAIL
    # ========================================================================
    
    def send_email_alert(self, new_regulations):
        """Send weekly email digest on Mondays only"""
        if not EMAIL_PASSWORD or EMAIL_PASSWORD == 'your-app-password':
            print("Email not configured")
            return
        
        # Only send on Mondays
        if datetime.now().weekday() != 0:
            print(f"Not Monday - skipping email")
            return
        
        # Get all new items from past week
        one_week_ago = datetime.now() - timedelta(days=7)
        weekly_new = [
            r for r in self.regulations 
            if r.get('isNew') and datetime.strptime(r['date'], '%Y-%m-%d') >= one_week_ago
        ]
        
        if not weekly_new:
            print("No new regulations this week")
            return
        
        try:
            env_regs = [r for r in weekly_new if r.get('category') == 'environmental']
            social_regs = [r for r in weekly_new if r.get('category') == 'social']
            
            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>📅 Weekly ESG Digest</h2>
                <p><strong>{len(weekly_new)} new regulations this week</strong></p>
                
                <h3>🌿 Environmental ({len(env_regs)})</h3>
                <ul>
                {''.join([f'<li><strong>{r["title"]}</strong><br>Source: {r["source_type"]}<br><a href="{r["source_url"]}">View</a></li>' for r in env_regs[:15]])}
                </ul>
                
                <h3>👥 Social ({len(social_regs)})</h3>
                <ul>
                {''.join([f'<li><strong>{r["title"]}</strong><br>Source: {r["source_type"]}<br><a href="{r["source_url"]}">View</a></li>' for r in social_regs[:15]])}
                </ul>
                
                <p><a href="https://isabelfields.github.io/esg-regulations-monitor/esg-regulations-monitor.html">View Dashboard</a></p>
            </body>
            </html>
            """
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f'📅 Weekly ESG Digest: {len(weekly_new)} New Regulations'
            msg['From'] = EMAIL_FROM
            msg['To'] = EMAIL_TO
            
            msg.attach(MIMEText(html_body, 'html'))
            
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(EMAIL_FROM, EMAIL_PASSWORD)
                server.send_message(msg)
            
            print(f"✅ Email sent")
        except Exception as e:
            print(f"Email error: {e}")
    
    # ========================================================================
    # RUN
    # ========================================================================
    
    def run(self):
        """Main monitoring"""
        print(f"\n{'='*70}")
        print(f"ESG Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")
        
        new_regulations = []
        
        print("ENVIRONMENTAL (Official + Reuters)")
        print("="*70)
        new_regulations.extend(self.check_sec_official())
        new_regulations.extend(self.check_federal_register())
        new_regulations.extend(self.check_eu_official())
        new_regulations.extend(self.check_issb_official())
        new_regulations.extend(self.check_fca_official())
        new_regulations.extend(self.check_canada_official())
        new_regulations.extend(self.check_reuters_environmental())
        
        print("\nSOCIAL (Official + Reuters)")
        print("="*70)
        new_regulations.extend(self.check_eeoc_official())
        new_regulations.extend(self.check_fcc_official())
        new_regulations.extend(self.check_reuters_social())
        
        # Mark old as not new
        for reg in self.regulations:
            reg['isNew'] = False
        
        print("\n" + "="*70)
        if new_regulations:
            env_count = len([r for r in new_regulations if r.get('category') == 'environmental'])
            social_count = len([r for r in new_regulations if r.get('category') == 'social'])
            
            print(f"✅ Found {len(new_regulations)} new regulation(s)")
            print(f"   Environmental: {env_count}")
            print(f"   Social: {social_count}")
            
            self.regulations.extend(new_regulations)
            self.save_regulations()
            self.send_email_alert(new_regulations)
        else:
            print("✅ No new regulations")
        
        print(f"\nTotal tracked: {len(self.regulations)}")
        print(f"{'='*70}\n")

if __name__ == '__main__':
    monitor = ESGMonitor()
    monitor.run()
