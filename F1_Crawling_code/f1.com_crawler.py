import asyncio
from playwright.async_api import async_playwright, TimeoutError
from bs4 import BeautifulSoup
import os
import time

f1_teams = {
    "Scuderia_Ferrari": "https://www.formula1.com/en/information/ferrari-year-by-year.61yfcjhl05vSlmNJB1SIJ0",
    "Red_Bull_Racing": "https://www.formula1.com/en/information/red-bull-racing-year-by-year.5gsBMoMf3DhOSBOJ8Cx8Bi",
    "McLaren": "https://www.formula1.com/en/information/mclaren-year-by-year.6Gj22qyOorq5dpniarY3rP",
    "Haas_F1_Team": "https://www.formula1.com/en/information/haas-year-by-year.7DczM4FtRLOOlbMMrMVSaE",
    "Sauber_Motorsport": "https://www.formula1.com/en/information/kick-sauber-year-by-year.JoWXFc6oEcNk5ozeiPxG5",
    "Aston_Martin_in_Formula_One": "https://www.formula1.com/en/information/aston-martin-year-by-year.69C4UPk1FrpRIzE7L4Py9n",
    "Mercedes-Benz_in_Formula_One": "https://www.formula1.com/en/information/mercedes-year-by-year.45gq1OShE3U1H5iEJSVtNd",
    "Williams_Racing": "https://www.formula1.com/en/information/williams-year-by-year.6wHlJglT3USpmIbETtAYzW",
    "Racing_Bulls": "https://www.formula1.com/en/information/rb-year-by-year.RsVCsWpMnPzUr7nNVSlyO",
    "Alpine_F1_Team": "https://www.formula1.com/en/information/alpine-year-by-year.26lcAj4zKxSs1w959B6yV"
}

html_content = None # 성공한 HTML을 담을 변수
# async 사용
async def crawl_and_save_text(team_key, url):
    source = "f1.com"
    file_name = f"{team_key}_{source}_data.txt"
    output_dir = f"(ENG)F1_{source}"
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                print(f"[ {source} ]에서 [ {team_key} ] 데이터 크롤링")
                
                response = await page.goto(url, timeout=30000)
                if response is None or response.status >= 400:
                    raise Exception(f"❌ HTTP 요청 실패: {response.status if response else 'N/A'}")

                # 쿠키 팝업 처리=======================================================
                try:
                    # 쿠키 팝업이 들어있는 iframe 찾기
                    iframe = page.frame_locator("iframe[id*='sp_message_iframe']")
                    # 쿠키 동의 버튼 클릭
                    await iframe.get_by_title("Accept all").click(timeout=5000)
                    print(f"👍 [{team_key}] 쿠키 동의 팝업 처리 성공")
                    await asyncio.sleep(2)

                except Exception as e:
                    print(f"❌ [{team_key}] 쿠키 동의 팝업 처리 실패: {str(e)}")
                    pass
                # ====================================================================
                    
                # 메인 콘텐츠 로딩 대기
                await page.wait_for_selector('#maincontent', state='attached', timeout=60000) 
                
                html_content = await page.content()

                print(f"👍 [{team_key}] 페이지 로딩 성공")
                
            except (TimeoutError, Exception) as e:                    
                if attempt == MAX_RETRIES - 1:
                    print(f"❌ [{team_key}] 페이지 로딩 최종 실패: {str(e)}")
                    await browser.close()
                    return None
                
                print(f"❌ [{team_key}] 페이지 로딩 실패: {str(e)} (남은 시도 횟수: {MAX_RETRIES - attempt - 1}회)")
                await asyncio.sleep(5)
                continue
                
            if not html_content:
                print(f"❌ [{team_key}] HTML 콘텐츠를 찾을 수 없습니다.")
                return None

            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 가장 안정적인 부모 컨테이너 찾기
            full_container = soup.select('div[class*="Container-module_inner"] div[class*="content-rich-text"]')
            # print(full_container)

            if not full_container:
                print(f"❌ [{team_key}] 최종 부모 컨테이너를 찾을 수 없습니다.")
                return None
                
            extracted_text = []
            
            for container in full_container:
                elements = container.select('h3, p')

                for element in elements:
                    # print(element)
                    # 노이즈(표, 각주, 이미지, 미디어) 제거 및 텍스트 제거
                    for tag in element.find_all(['a', 'img', 'table']): tag.decompose()

                    text = element.get_text(strip=True)
                    # print(text)
                    if text:
                        if element.name in ['h2', 'h3']:
                            extracted_text.append(f"\n--- {element.name.upper()}: {text} ---")
                        else:
                            extracted_text.append(text)                    
                # print(extracted_text)

            # 결과를 TXT 파일로 저장
            full_path = os.path.join(output_dir, file_name)

            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(f"URL: {url}\n\n")
                f.write(f"팀 이름: {team_key} \n")
                f.write(f"========== TEAM NARRATIVE DATA ({source}) ==========\n")
                f.write('\n'.join(extracted_text))
            
            print(f"✅ [{team_key}] 데이터 크롤링 및 저장이 완료되었습니다: {full_path}")
            return full_path

    except Exception as e:
        # 타임아웃 오류 시 브라우저가 닫히지 않았을 수 있으므로 안전하게 닫기 시도
        try:
            await browser.close() 
        except:
            pass
        print(f"❌ [{team_key}] 크롤링 중 예외 발생: {e}")
        return None

# --- 실행 ---
# Playwright는 비동기 환경에서 실행해야 함
async def main_async():
    print("크롤링을 시작합니다...\n")

    tasks = []
    for team_key, url in f1_teams.items():
        # 각 팀에 대한 크롤링 작업을 tasks 리스트에 담는다.
        tasks.append(crawl_and_save_text(team_key, url))
    
    # 핵심: asyncio.gather를 await로 실행!
    # 이 부분이 비동기(async) 함수 내부에서 실행되어야 한다.
    await asyncio.gather(*tasks) 
    
    print("\n모든 팀에 대한 크롤링 작업이 완료되었습니다.")

if __name__ == "__main__":
    # asyncio.run()은 최상위 비동기 함수(main_async)만 실행한다.
    asyncio.run(main_async())