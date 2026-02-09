#!/usr/bin/env python3
"""
ESG Regulations Backfill Script
Populates regulations.json with historical data from Jan 1, 2025 to present
Uses Google News searches with date filtering
"""

import feedparser
import json
from datetime import datetime
from pathlib import Path
import time

class ESGBackfill:
    def __init__(self):
        self.regulations = []
        self.regulations_file = Path('regulations.json')
    
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
        """Determine priority"""
        text = f"{title} {description}".lower()
        if any(w in text for w in ['final', 'adopted', 'enacted', 'injunction', 'lawsuit']):
            return 'critical'
        elif any(w in text for w in ['proposed', 'draft']):
            return 'high'
        return 'medium'
    
    def extract_tags(self, title, description):
        """Extract tags"""
        text = f"{title} {description}".lower()
        tags = []
        
        tag_map = {
            'Climate': ['climate', 'emissions'],
            'CSRD': ['csrd'],
            'ISSB': ['issb'],
            'SB 253': ['sb 253', 'sb253'],
            'EEOC': ['eeoc'],
            'Discrimination': ['discrimination'],
        }
        
        for tag, keywords in tag_map.items():
            if any(kw in text for kw in keywords):
                tags.append(tag)
        
        return tags[:5]
    
    def check_google_news_search(self, query, category, source_category, jurisdiction):
        """Generic Google News search"""
        print(f"  Searching: {query[:50]}...")
        new_items = []
        
        # Google News RSS with query
        feed_url = f'https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en'
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:50]:  # Check top 50
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                combined = f"{title} {description}".lower()
                
                # Block junk
                is_junk = any(phrase in combined for phrase in [
                    'what employers should know', 'what companies should know',
                    'guide to', 'how to', 'webinar', 'podcast',
                    'laboremploymentlawblog', 'day 1', 'rejoins', 'deputy director'
                ])
                
                if not is_junk and not any(r['title'] == title for r in self.regulations):
                    pub_date = entry.get('published', entry.get('updated', ''))
                    parsed_date = self.parse_date(pub_date)
                    
                    if not self.is_recent_enough(parsed_date):
                        continue
                    
                    new_items.append({
                        'id': len(self.regulations) + len(new_items) + 1,
                        'title': title,
                        'category': category,
                        'source_category': source_category,
                        'jurisdiction': jurisdiction,
                        'type': 'enforcement' if 'lawsuit' in combined or 'settlement' in combined else 'disclosure',
                        'priority': self.categorize_priority(title, description),
                        'date': parsed_date,
                        'isNew': True,
                        'description': description[:500] + ('...' if len(description) > 500 else ''),
                        'tags': self.extract_tags(title, description),
                        'effectiveDate': 'TBD',
                        'source_url': entry.get('link', ''),
                        'source_type': 'Google News Backfill'
                    })
            
            print(f"    Found {len(new_items)} items")
            time.sleep(2)  # Rate limit
        
        except Exception as e:
            print(f"    Error: {e}")
        
        return new_items
    
    def backfill_environmental(self):
        """Backfill environmental regulations"""
        print("\n" + "="*70)
        print("BACKFILLING ENVIRONMENTAL REGULATIONS (Jan 2025 - Present)")
        print("="*70)
        
        searches = [
            # SEC Climate
            ('SEC+climate+disclosure+rule', 'environmental', 'sec-backfill', 'sec'),
            ('SEC+adopts+climate+OR+sustainability', 'environmental', 'sec-backfill', 'sec'),
            
            # California SB 253/261
            ('SB+253+California+climate', 'environmental', 'california-backfill', 'california'),
            ('SB+261+California+climate', 'environmental', 'california-backfill', 'california'),
            ('"SB+253"+injunction+OR+lawsuit', 'environmental', 'california-backfill', 'california'),
            
            # EU CSRD
            ('CSRD+EU+sustainability+reporting', 'environmental', 'eu-backfill', 'eu'),
            ('EU+ESRS+sustainability+standards', 'environmental', 'eu-backfill', 'eu'),
            
            # ISSB
            ('ISSB+climate+disclosure+standard', 'environmental', 'issb-backfill', 'international'),
            ('IFRS+S1+OR+S2+sustainability', 'environmental', 'issb-backfill', 'international'),
            
            # UK SDR
            ('UK+FCA+sustainability+disclosure', 'environmental', 'uk-backfill', 'uk'),
            
            # Greenwashing enforcement
            ('SEC+greenwashing+enforcement+OR+charges', 'environmental', 'sec-backfill', 'sec'),
        ]
        
        for query, cat, src_cat, juris in searches:
            items = self.check_google_news_search(query, cat, src_cat, juris)
            self.regulations.extend(items)
    
    def backfill_social(self):
        """Backfill social/DEI regulations"""
        print("\n" + "="*70)
        print("BACKFILLING SOCIAL REGULATIONS (Jan 2025 - Present)")
        print("="*70)
        
        searches = [
            # EEOC
            ('EEOC+lawsuit+OR+settlement+discrimination', 'social', 'eeoc-backfill', 'eeoc'),
            ('EEOC+investigation+OR+charges', 'social', 'eeoc-backfill', 'eeoc'),
            ('EEOC+files+lawsuit', 'social', 'eeoc-backfill', 'eeoc'),
            
            # Pay equity
            ('pay+transparency+law+enacted+OR+passed', 'social', 'state-dei-backfill', 'state-dei'),
            ('pay+equity+disclosure+requirement', 'social', 'state-dei-backfill', 'state-dei'),
            
            # Board diversity
            ('board+diversity+mandate+OR+requirement', 'social', 'inclusion-backfill', 'inclusion'),
            ('Nasdaq+diversity+rule', 'social', 'inclusion-backfill', 'inclusion'),
            
            # FCC DEI
            ('FCC+diversity+OR+investigation+DEI', 'social', 'fcc-backfill', 'fcc'),
            
            # ADA lawsuits
            ('ADA+lawsuit+website+accessibility', 'social', 'ada-backfill', 'ada'),
            ('ADA+settlement+accessibility', 'social', 'ada-backfill', 'ada'),
            
            # Executive orders
            ('executive+order+DEI+OR+diversity', 'social', 'executive-order-backfill', 'executive-order'),
        ]
        
        for query, cat, src_cat, juris in searches:
            items = self.check_google_news_search(query, cat, src_cat, juris)
            self.regulations.extend(items)
    
    def deduplicate(self):
        """Remove duplicates by title"""
        print("\nDeduplicating...")
        seen_titles = set()
        unique_regs = []
        
        for reg in self.regulations:
            if reg['title'] not in seen_titles:
                seen_titles.add(reg['title'])
                unique_regs.append(reg)
        
        removed = len(self.regulations) - len(unique_regs)
        print(f"  Removed {removed} duplicates")
        self.regulations = unique_regs
        
        # Re-number IDs
        for idx, reg in enumerate(self.regulations, 1):
            reg['id'] = idx
    
    def save(self):
        """Save to regulations.json"""
        try:
            with open(self.regulations_file, 'w', encoding='utf-8') as f:
                json.dump(self.regulations, f, indent=2, ensure_ascii=False)
            print(f"\n✅ Saved {len(self.regulations)} regulations to {self.regulations_file}")
        except Exception as e:
            print(f"❌ Error saving: {e}")
    
    def run(self):
        """Run backfill"""
        print("\n" + "="*70)
        print("ESG REGULATIONS BACKFILL")
        print("Searching Jan 1, 2025 - Present")
        print("="*70)
        
        self.backfill_environmental()
        self.backfill_social()
        
        self.deduplicate()
        
        # Sort by date (newest first)
        self.regulations.sort(key=lambda x: x['date'], reverse=True)
        
        # Stats
        env_count = len([r for r in self.regulations if r['category'] == 'environmental'])
        social_count = len([r for r in self.regulations if r['category'] == 'social'])
        
        print("\n" + "="*70)
        print(f"BACKFILL COMPLETE")
        print(f"  Environmental: {env_count}")
        print(f"  Social: {social_count}")
        print(f"  Total: {len(self.regulations)}")
        print("="*70)
        
        self.save()

if __name__ == '__main__':
    backfill = ESGBackfill()
    backfill.run()
