#!/usr/bin/env python3
"""
ESG Regulatory Monitor
Automated monitoring script that checks SEC, EU, and state sources
and updates the web dashboard with real data.
"""

import feedparser
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import re
from pathlib import Path

# Configuration
EMAIL_FROM = os.getenv('EMAIL_FROM', 'your-email@gmail.com')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', 'your-app-password')
EMAIL_TO = os.getenv('EMAIL_TO', 'compliance-team@company.com').split(',')

# Keywords for filtering ESG-related content
ESG_KEYWORDS = [
    'climate', 'esg', 'sustainability', 'disclosure', 'greenhouse', 'emissions',
    'csrd', 'taxonomy', 'sfdr', 'carbon', 'environmental', 'social', 'governance',
    'tcfd', 'scope 1', 'scope 2', 'scope 3', 'net zero', 'transition plan',
    # California Bills
    'sb 253', 'sb 261', 'sb253', 'sb261', 'senate bill 253', 'senate bill 261',
    'climate corporate data accountability', 'climate-related financial risk',
    # CSRD & EU
    'corporate sustainability reporting directive', 'esrs', 'european sustainability reporting',
    'csrd implementation', 'double materiality',
    # TCFD
    'task force on climate-related financial disclosures', 'tcfd framework',
    'tcfd recommendations', 'tcfd alignment',
    # ISSB / IFRS
    'issb', 'ifrs s1', 'ifrs s2', 'sustainability disclosure standards',
    'international sustainability standards board', 'ifrs foundation',
    # UK SDR
    'sustainability disclosure requirements', 'sdr', 'fca sustainability',
    # Canada
    'canada climate disclosure', 'canadian securities administrators', 'csa climate',
    'nі 51-107', 'ni 58-101',
    # Asia
    'singapore climate disclosure', 'hong kong climate', 'japan tcfd',
    'korea esg', 'china esg disclosure', 'asean taxonomy',
    'mas climate', 'hkex esg', 'issb adoption asia'
]

STATE_KEYWORDS = ESG_KEYWORDS + ['climate change', 'environmental justice', 'carb']

class RegulationMonitor:
    def __init__(self):
        self.regulations_file = Path('regulations.json')
        self.dashboard_file = Path('esg-monitor.html')
        self.regulations = self.load_regulations()
        
    def load_regulations(self):
        """Load existing regulations from JSON file"""
        if self.regulations_file.exists():
            with open(self.regulations_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def save_regulations(self):
        """Save regulations to JSON file"""
        with open(self.regulations_file, 'w', encoding='utf-8') as f:
            json.dump(self.regulations, f, indent=2, ensure_ascii=False)
    
    def is_esg_related(self, text):
        """Check if text contains ESG-related keywords"""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in ESG_KEYWORDS)
    
    def categorize_priority(self, title, description):
        """Determine priority level based on content"""
        text = f"{title} {description}".lower()
        
        critical_terms = ['required', 'mandatory', 'final rule', 'enforcement', 'deadline']
        high_terms = ['proposed', 'amendment', 'update', 'new requirement']
        
        if any(term in text for term in critical_terms):
            return 'critical'
        elif any(term in text for term in high_terms):
            return 'high'
        return 'medium'
    
    def categorize_type(self, title, description):
        """Determine regulation type"""
        text = f"{title} {description}".lower()
        
        if 'disclosure' in text or 'reporting' in text:
            return 'disclosure'
        elif 'taxonomy' in text or 'classification' in text:
            return 'taxonomy'
        elif 'enforcement' in text or 'penalty' in text:
            return 'enforcement'
        return 'reporting'
    
    def extract_tags(self, title, description):
        """Extract relevant tags from content"""
        text = f"{title} {description}".lower()
        tags = []
        
        tag_patterns = {
            'Climate': ['climate', 'greenhouse', 'emissions', 'carbon'],
            'GHG Emissions': ['ghg', 'greenhouse gas', 'scope 1', 'scope 2', 'scope 3'],
            'Disclosure': ['disclosure', 'reporting requirement'],
            'Supply Chain': ['supply chain', 'value chain', 'upstream', 'downstream'],
            'TCFD': ['tcfd', 'task force'],
            'Taxonomy': ['taxonomy', 'classification'],
            'Due Diligence': ['due diligence', 'human rights'],
            'Annual Reports': ['annual report', '10-k', 'form 10-k'],
            'CSRD': ['csrd', 'corporate sustainability reporting'],
            'ESRS': ['esrs', 'sustainability reporting standard']
        }
        
        for tag, keywords in tag_patterns.items():
            if any(kw in text for kw in keywords):
                tags.append(tag)
        
        return tags[:5]  # Limit to 5 tags
    
    def check_sec_feed(self):
        """Monitor SEC press releases and rule updates"""
        print("Checking SEC updates...")
        new_items = []
        
        feeds = [
            ('https://www.sec.gov/news/pressreleases.rss', 'Press Release'),
            ('https://www.sec.gov/rss/news/press.xml', 'News')
        ]
        
        for feed_url, source_type in feeds:
            try:
                feed = feedparser.parse(feed_url)
                
                for entry in feed.entries[:20]:  # Check last 20 items
                    title = entry.get('title', '')
                    description = entry.get('summary', entry.get('description', ''))
                    
                    if self.is_esg_related(title + ' ' + description):
                        # Check if already exists
                        if not any(r['title'] == title for r in self.regulations):
                            pub_date = entry.get('published', entry.get('updated', ''))
                            
                            regulation = {
                                'id': len(self.regulations) + len(new_items) + 1,
                                'title': title,
                                'jurisdiction': 'sec',
                                'type': self.categorize_type(title, description),
                                'priority': self.categorize_priority(title, description),
                                'date': self.parse_date(pub_date),
                                'isNew': True,
                                'description': description[:500] + ('...' if len(description) > 500 else ''),
                                'tags': self.extract_tags(title, description),
                                'effectiveDate': 'TBD',
                                'source_url': entry.get('link', ''),
                                'source_type': source_type
                            }
                            new_items.append(regulation)
                            print(f"  Found: {title[:60]}...")
            
            except Exception as e:
                print(f"  Error parsing {feed_url}: {e}")
        
        return new_items
    
    def check_eu_feed(self):
        """Monitor EUR-Lex for EU regulations"""
        print("Checking EU updates...")
        new_items = []
        
        feed_url = 'https://eur-lex.europa.eu/EN/display-feed.do?do-feed=allnew'
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:30]:  # Check last 30 items
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                
                if self.is_esg_related(title + ' ' + description):
                    if not any(r['title'] == title for r in self.regulations):
                        pub_date = entry.get('published', entry.get('updated', ''))
                        
                        regulation = {
                            'id': len(self.regulations) + len(new_items) + 1,
                            'title': title,
                            'jurisdiction': 'eu',
                            'type': self.categorize_type(title, description),
                            'priority': self.categorize_priority(title, description),
                            'date': self.parse_date(pub_date),
                            'isNew': True,
                            'description': description[:500] + ('...' if len(description) > 500 else ''),
                            'tags': self.extract_tags(title, description),
                            'effectiveDate': 'TBD',
                            'source_url': entry.get('link', ''),
                            'source_type': 'EUR-Lex'
                        }
                        new_items.append(regulation)
                        print(f"  Found: {title[:60]}...")
        
        except Exception as e:
            print(f"  Error parsing EUR-Lex feed: {e}")
        
        return new_items
    
    def check_california_legislature(self):
        """Monitor California legislation (SB 253, SB 261, and other ESG bills)"""
        print("Checking California legislation...")
        new_items = []
        
        # California Air Resources Board (CARB) - Implements SB 253
        carb_sources = [
            ('https://ww2.arb.ca.gov/rss.xml', 'CARB General'),
        ]
        
        for feed_url, source_type in carb_sources:
            try:
                feed = feedparser.parse(feed_url)
                
                for entry in feed.entries[:15]:
                    title = entry.get('title', '')
                    description = entry.get('summary', entry.get('description', ''))
                    
                    # Look for SB 253, SB 261, or general ESG content
                    if (self.is_esg_related(title + ' ' + description) or
                        'sb 253' in title.lower() or 'sb253' in title.lower() or
                        'sb 261' in title.lower() or 'sb261' in title.lower() or
                        'climate disclosure' in title.lower()):
                        
                        if not any(r['title'] == title for r in self.regulations):
                            pub_date = entry.get('published', entry.get('updated', ''))
                            
                            regulation = {
                                'id': len(self.regulations) + len(new_items) + 1,
                                'title': title,
                                'jurisdiction': 'california',
                                'type': self.categorize_type(title, description),
                                'priority': self.categorize_priority(title, description),
                                'date': self.parse_date(pub_date),
                                'isNew': True,
                                'description': description[:500] + ('...' if len(description) > 500 else ''),
                                'tags': self.extract_tags(title, description) + ['SB 253/261'],
                                'effectiveDate': 'TBD',
                                'source_url': entry.get('link', ''),
                                'source_type': source_type
                            }
                            new_items.append(regulation)
                            print(f"  Found: {title[:60]}...")
            
            except Exception as e:
                print(f"  Error parsing {feed_url}: {e}")
        
        return new_items
    
    def check_issb_ifrs(self):
        """Monitor ISSB and IFRS Sustainability Standards (S1 & S2)"""
        print("Checking ISSB/IFRS updates...")
        new_items = []
        
        # IFRS Foundation news feed
        feed_url = 'https://www.ifrs.org/news-and-events/news.xml'
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:20]:
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                
                # Filter for ISSB/sustainability content
                if (self.is_esg_related(title + ' ' + description) or
                    'issb' in title.lower() or 'ifrs s1' in title.lower() or 
                    'ifrs s2' in title.lower() or 'sustainability standards' in title.lower()):
                    
                    if not any(r['title'] == title for r in self.regulations):
                        pub_date = entry.get('published', entry.get('updated', ''))
                        
                        regulation = {
                            'id': len(self.regulations) + len(new_items) + 1,
                            'title': title,
                            'jurisdiction': 'international',
                            'type': 'reporting',
                            'priority': self.categorize_priority(title, description),
                            'date': self.parse_date(pub_date),
                            'isNew': True,
                            'description': description[:500] + ('...' if len(description) > 500 else ''),
                            'tags': self.extract_tags(title, description) + ['ISSB', 'IFRS'],
                            'effectiveDate': 'TBD',
                            'source_url': entry.get('link', ''),
                            'source_type': 'IFRS Foundation'
                        }
                        new_items.append(regulation)
                        print(f"  Found: {title[:60]}...")
        
        except Exception as e:
            print(f"  Error parsing IFRS feed: {e}")
        
        return new_items
    
    def check_uk_fca(self):
        """Monitor UK FCA Sustainability Disclosure Requirements (SDR)"""
        print("Checking UK FCA/SDR updates...")
        new_items = []
        
        # FCA news feed
        feed_url = 'https://www.fca.org.uk/news/news.rss'
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:20]:
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                
                # Filter for sustainability/ESG content
                if (self.is_esg_related(title + ' ' + description) or
                    'sdr' in title.lower() or 'sustainability disclosure' in title.lower()):
                    
                    if not any(r['title'] == title for r in self.regulations):
                        pub_date = entry.get('published', entry.get('updated', ''))
                        
                        regulation = {
                            'id': len(self.regulations) + len(new_items) + 1,
                            'title': title,
                            'jurisdiction': 'uk',
                            'type': self.categorize_type(title, description),
                            'priority': self.categorize_priority(title, description),
                            'date': self.parse_date(pub_date),
                            'isNew': True,
                            'description': description[:500] + ('...' if len(description) > 500 else ''),
                            'tags': self.extract_tags(title, description) + ['UK SDR', 'FCA'],
                            'effectiveDate': 'TBD',
                            'source_url': entry.get('link', ''),
                            'source_type': 'FCA'
                        }
                        new_items.append(regulation)
                        print(f"  Found: {title[:60]}...")
        
        except Exception as e:
            print(f"  Error parsing FCA feed: {e}")
        
        return new_items
    
    def check_canada_securities(self):
        """Monitor Canadian Securities Administrators climate disclosures"""
        print("Checking Canadian climate disclosure updates...")
        new_items = []
        
        # CSA publishes to multiple provincial regulators
        # OSC (Ontario) is the largest and most active
        feed_url = 'https://www.osc.ca/en/news-events/news.rss'
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:20]:
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                
                if (self.is_esg_related(title + ' ' + description) or
                    'csa' in title.lower() or 'ni 51-107' in title.lower() or
                    'ni 58-101' in title.lower()):
                    
                    if not any(r['title'] == title for r in self.regulations):
                        pub_date = entry.get('published', entry.get('updated', ''))
                        
                        regulation = {
                            'id': len(self.regulations) + len(new_items) + 1,
                            'title': title,
                            'jurisdiction': 'canada',
                            'type': self.categorize_type(title, description),
                            'priority': self.categorize_priority(title, description),
                            'date': self.parse_date(pub_date),
                            'isNew': True,
                            'description': description[:500] + ('...' if len(description) > 500 else ''),
                            'tags': self.extract_tags(title, description) + ['CSA', 'Canada'],
                            'effectiveDate': 'TBD',
                            'source_url': entry.get('link', ''),
                            'source_type': 'OSC/CSA'
                        }
                        new_items.append(regulation)
                        print(f"  Found: {title[:60]}...")
        
        except Exception as e:
            print(f"  Error parsing OSC/CSA feed: {e}")
        
        return new_items
    
    def check_asia_pacific(self):
        """Monitor Asia-Pacific climate disclosure regulations"""
        print("Checking Asia-Pacific updates...")
        new_items = []
        
        # Singapore MAS
        mas_url = 'https://www.mas.gov.sg/rss-feeds/news-releases.xml'
        
        # Hong Kong HKEX
        hkex_url = 'https://www.hkex.com.hk/rss/market/listco.xml'
        
        sources = [
            (mas_url, 'MAS Singapore'),
            (hkex_url, 'HKEX Hong Kong')
        ]
        
        for feed_url, source_name in sources:
            try:
                feed = feedparser.parse(feed_url)
                
                for entry in feed.entries[:15]:
                    title = entry.get('title', '')
                    description = entry.get('summary', entry.get('description', ''))
                    
                    if self.is_esg_related(title + ' ' + description):
                        if not any(r['title'] == title for r in self.regulations):
                            pub_date = entry.get('published', entry.get('updated', ''))
                            
                            # Determine jurisdiction from source
                            jurisdiction = 'singapore' if 'MAS' in source_name else 'hong-kong'
                            
                            regulation = {
                                'id': len(self.regulations) + len(new_items) + 1,
                                'title': title,
                                'jurisdiction': jurisdiction,
                                'type': self.categorize_type(title, description),
                                'priority': self.categorize_priority(title, description),
                                'date': self.parse_date(pub_date),
                                'isNew': True,
                                'description': description[:500] + ('...' if len(description) > 500 else ''),
                                'tags': self.extract_tags(title, description) + ['Asia-Pacific'],
                                'effectiveDate': 'TBD',
                                'source_url': entry.get('link', ''),
                                'source_type': source_name
                            }
                            new_items.append(regulation)
                            print(f"  Found: {title[:60]}...")
            
            except Exception as e:
                print(f"  Error parsing {source_name} feed: {e}")
        
        return new_items
    
    
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
    
    def send_email_alert(self, new_regulations):
        """Send email alert for new regulations"""
        if not new_regulations or not EMAIL_PASSWORD or EMAIL_PASSWORD == 'your-app-password':
            print("Skipping email (no new regulations or email not configured)")
            return
        
        print(f"Sending email alert for {len(new_regulations)} new regulation(s)...")
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f'🚨 ESG Alert: {len(new_regulations)} New Regulation{"s" if len(new_regulations) > 1 else ""}'
            msg['From'] = EMAIL_FROM
            msg['To'] = ', '.join(EMAIL_TO)
            
            # Create text version
            text_body = f"New ESG Regulations Detected ({len(new_regulations)}):\n\n"
            
            for reg in new_regulations:
                text_body += f"• {reg['title']}\n"
                text_body += f"  Jurisdiction: {reg['jurisdiction'].upper()}\n"
                text_body += f"  Priority: {reg['priority'].upper()}\n"
                text_body += f"  Date: {reg['date']}\n"
                if reg.get('source_url'):
                    text_body += f"  Link: {reg['source_url']}\n"
                text_body += "\n"
            
            text_body += "\nView full dashboard: [Open your local esg-monitor.html file]\n"
            
            # Create HTML version
            html_body = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                    .header {{ background: #0a3d2e; color: white; padding: 20px; }}
                    .regulation {{ background: #f9f9f9; padding: 15px; margin: 10px 0; border-left: 4px solid #e8ff00; }}
                    .priority-critical {{ border-left-color: #ff3b30; }}
                    .priority-high {{ border-left-color: #ff9500; }}
                    .priority-medium {{ border-left-color: #ffcc00; }}
                    .badge {{ display: inline-block; padding: 3px 8px; border-radius: 3px; font-size: 12px; margin-right: 5px; }}
                    .badge-jurisdiction {{ background: #0a3d2e; color: white; }}
                    .badge-priority {{ background: #e8ff00; color: #0a3d2e; font-weight: bold; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>🚨 ESG Regulatory Alert</h1>
                    <p>{len(new_regulations)} new regulation{"s" if len(new_regulations) > 1 else ""} require{"" if len(new_regulations) > 1 else "s"} your attention</p>
                </div>
            """
            
            for reg in new_regulations:
                html_body += f"""
                <div class="regulation priority-{reg['priority']}">
                    <h2>{reg['title']}</h2>
                    <div>
                        <span class="badge badge-jurisdiction">{reg['jurisdiction'].upper()}</span>
                        <span class="badge badge-priority">{reg['priority'].upper()} PRIORITY</span>
                    </div>
                    <p><strong>Date:</strong> {reg['date']}</p>
                    <p>{reg['description']}</p>
                    <p><a href="{reg.get('source_url', '#')}">View Source →</a></p>
                </div>
                """
            
            html_body += """
                <p style="margin-top: 30px; padding: 20px; background: #f0f0f0;">
                    <strong>Next Steps:</strong><br>
                    1. Review regulations in your local dashboard<br>
                    2. Assess impact on your organization<br>
                    3. Update compliance calendar
                </p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(text_body, 'plain'))
            msg.attach(MIMEText(html_body, 'html'))
            
            # Send via Gmail
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(EMAIL_FROM, EMAIL_PASSWORD)
                server.send_message(msg)
            
            print("  Email sent successfully!")
        
        except Exception as e:
            print(f"  Error sending email: {e}")
    
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
            js_data = json.dumps(self.regulations, indent=8)
            
            # Replace the regulations array in the JavaScript
            pattern = r'const regulations = \[.*?\];'
            replacement = f'const regulations = {js_data};'
            
            updated_html = re.sub(pattern, replacement, html_content, flags=re.DOTALL)
            
            with open(self.dashboard_file, 'w', encoding='utf-8') as f:
                f.write(updated_html)
            
            print(f"  Dashboard updated with {len(self.regulations)} regulations")
        
        except Exception as e:
            print(f"  Error updating dashboard: {e}")
    
    def run(self):
        """Main monitoring loop"""
        print(f"\n{'='*60}")
        print(f"ESG Regulatory Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        # Collect new regulations from all sources
        new_regulations = []
        
        # US Federal
        new_regulations.extend(self.check_sec_feed())
        
        # EU
        new_regulations.extend(self.check_eu_feed())
        
        # US State (California SB 253/261)
        new_regulations.extend(self.check_california_legislature())
        
        # International Standards
        new_regulations.extend(self.check_issb_ifrs())
        
        # UK
        new_regulations.extend(self.check_uk_fca())
        
        # Canada
        new_regulations.extend(self.check_canada_securities())
        
        # Asia-Pacific
        new_regulations.extend(self.check_asia_pacific())
        
        # Mark older regulations as not new
        for reg in self.regulations:
            reg['isNew'] = False
        
        # Add new regulations
        if new_regulations:
            print(f"\n✅ Found {len(new_regulations)} new regulation(s)")
            self.regulations.extend(new_regulations)
            self.save_regulations()
            self.update_dashboard()
            self.send_email_alert(new_regulations)
        else:
            print("\n✅ No new regulations found")
        
        print(f"\nTotal regulations tracked: {len(self.regulations)}")
        print(f"{'='*60}\n")


if __name__ == '__main__':
    monitor = RegulationMonitor()
    monitor.run()
