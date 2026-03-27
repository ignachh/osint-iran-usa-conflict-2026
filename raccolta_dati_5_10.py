import asyncio
import pandas as pd
from playwright.async_api import async_playwright
import urllib.parse
import json
import os
import re
from datetime import datetime, timedelta, timezone
import random

QUERY_BASE_ITALIA = '(Iran OR Israele OR "guerra Iran" OR "attacco Iran" OR IranIsraele OR UNIFIL OR Hormuz OR Khamenei) lang:it'
tz_cet = timezone(timedelta(hours=1))

DATA_INIZIO = datetime(2026, 2, 28, 0, 0, 0, tzinfo=tz_cet)
DATA_FINE = datetime(2026, 3, 5, 7, 0, 0, tzinfo=tz_cet)
STEP_ORE = 8
MAX_TWEETS_PER_FASCIA = 500
COOKIES_FILE = "x_cookies_chrome.json"

async def raccogli_tweet_per_fascia(page, query_base, inizio_fascia, fine_fascia, max_tweets, nome_file_csv):
    unix_inizio = int(inizio_fascia.timestamp())
    unix_fine = int(fine_fascia.timestamp())
    
    query_fascia = f'{query_base} since_time:{unix_inizio} until_time:{unix_fine}'
    print(f"\n--- Fascia: {inizio_fascia.strftime('%d/%m %H:%M')} -> {fine_fascia.strftime('%H:%M')} ---")
    
    query_encoded = urllib.parse.quote(query_fascia)
    url = f"https://x.com/search?q={query_encoded}&src=typed_query"
    
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(random.uniform(4000, 7000))
    
    id_visti = set()
    tweets_raccolti_fascia = 0
    scroll_senza_nuovi = 0
    
    if os.path.exists(nome_file_csv):
        df_esistente = pd.read_csv(nome_file_csv, low_memory=False)
        id_visti.update(df_esistente['id'].astype(str).tolist())
    
    while tweets_raccolti_fascia < max_tweets:
        tweet_elements = await page.query_selector_all('[data-testid="tweet"]')
        nuovi_in_questo_scroll = 0
        batch_tweets = []
        
        for element in tweet_elements:
            try:
                link_element = await element.query_selector('a[href*="/status/"]')
                if not link_element: continue
                href = await link_element.get_attribute("href")
                tweet_id = href.split("/status/")[1].split("/")[0].split("?")[0]
                
                if tweet_id in id_visti: continue
                
                testo_element = await element.query_selector('[data-testid="tweetText"]')
                testo = await testo_element.inner_text() if testo_element else ""
                
                username = href.split("/")[1] if href.startswith("/") else ""
                mentions = re.findall(r'@(\w+)', testo)
                mentions_str = ",".join(mentions)
                
                in_reply_to = ""
                reply_element = await element.query_selector('div.r-111h2gw a[href^="/"]')
                if reply_element:
                    reply_href = await reply_element.get_attribute("href")
                    in_reply_to = reply_href.replace("/", "")
                
                time_element = await element.query_selector("time")
                data_ora = await time_element.get_attribute("datetime") if time_element else ""
                
                async def get_metrica(testid):
                    el = await element.query_selector(f'[data-testid="{testid}"]')
                    if el:
                        testo_el = await el.inner_text()
                        numeri = ''.join(filter(str.isdigit, testo_el.split('\n')[0]))
                        return int(numeri) if numeri else 0
                    return 0
                
                retweet  = await get_metrica("retweet")
                like     = await get_metrica("like")
                risposte = await get_metrica("reply")
                
                record = {
                    "id": tweet_id, "data_ora": data_ora, "username": username,
                    "testo": testo, "mentions": mentions_str, "in_reply_to": in_reply_to,
                    "retweet": retweet, "like": like, "risposte": risposte,
                    "url": f"https://x.com{href}"
                }
                
                batch_tweets.append(record)
                id_visti.add(tweet_id)
                nuovi_in_questo_scroll += 1
                tweets_raccolti_fascia += 1
                
            except Exception:
                continue
        
        if batch_tweets:
            df_batch = pd.DataFrame(batch_tweets)
            header = not os.path.exists(nome_file_csv)
            df_batch.to_csv(nome_file_csv, mode='a', header=header, index=False, encoding="utf-8-sig")
            
        print(f"    Progresso fascia: {tweets_raccolti_fascia}/{max_tweets} (Trovati {nuovi_in_questo_scroll} Top Tweets)")
        
        if nuovi_in_questo_scroll == 0:
            scroll_senza_nuovi += 1
        else:
            scroll_senza_nuovi = 0
            
        if scroll_senza_nuovi >= 5:
            print("    Nessun nuovo tweet rilevante dopo 5 scroll. Limite raggiunto.")
            break
            
        await page.evaluate("window.scrollBy(0, 1000 + Math.random() * 500)")
        await page.wait_for_timeout(random.uniform(3000, 5000))
        
    return tweets_raccolti_fascia

async def gestore_raccolta(playwright, query_base, nome_corpus, file_output):
    print(f"\n=== INIZIO RACCOLTA: {nome_corpus} ===")
    
    browser = await playwright.chromium.launch(headless=False, slow_mo=100)
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 800}
    )
    
    with open(COOKIES_FILE, "r") as f:
        cookies_raw = json.load(f)
    
    cookies_adattati = []
    for cookie in cookies_raw:
        c = {
            "name": cookie.get("name", ""), "value": cookie.get("value", ""),
            "domain": cookie.get("domain", ".x.com"), "path": cookie.get("path", "/"),
            "sameSite": cookie.get("sameSite", "Lax") if cookie.get("sameSite") in ["Strict", "Lax", "None"] else "Lax"
        }
        if "expirationDate" in cookie: c["expires"] = int(cookie["expirationDate"])
        cookies_adattati.append(c)
    
    await context.add_cookies(cookies_adattati)
    page = await context.new_page()
    
    finestra_corrente_inizio = DATA_INIZIO
    totale_corpus = 0
    
    while finestra_corrente_inizio < DATA_FINE:
        finestra_corrente_fine = finestra_corrente_inizio + timedelta(hours=STEP_ORE)
        if finestra_corrente_fine > DATA_FINE:
            finestra_corrente_fine = DATA_FINE
            
        # --- BLOCCO ANTI-DISCONNESSIONE ---
        successo = False
        tentativi = 0
        
        while not successo and tentativi < 5:
            try:
                totale_fascia = await raccogli_tweet_per_fascia(
                    page, query_base, finestra_corrente_inizio, finestra_corrente_fine, MAX_TWEETS_PER_FASCIA, file_output
                )
                totale_corpus += totale_fascia
                successo = True # Se arriva qui, non ci sono stati errori di rete
            except Exception as e:
                tentativi += 1
                print(f"\n[ATTENZIONE] Errore di connessione o Timeout (Tentativo {tentativi}/5). Attendo 60 secondi...")
                await asyncio.sleep(60)
                # Ricarica la pagina base di x per sbloccare eventuali freeze
                try: await page.goto("https://x.com", timeout=30000) 
                except: pass
                
        if not successo:
            print(f"\n[ERRORE CRITICO] Impossibile recuperare la fascia {finestra_corrente_inizio} dopo 5 tentativi. Salto alla successiva.")
        # ------------------------------------
        
        finestra_corrente_inizio = finestra_corrente_fine
        await page.wait_for_timeout(random.uniform(8000, 12000))
        
    await browser.close()
    print(f"Raccolta completata per {nome_corpus}. Totale salvato: {totale_corpus}")

async def main():
    async with async_playwright() as p:
        await gestore_raccolta(p, QUERY_BASE_ITALIA, "CORPUS ITALIA FASE 1", "corpus_italia_fase1.csv")

if __name__ == "__main__":
    asyncio.run(main())