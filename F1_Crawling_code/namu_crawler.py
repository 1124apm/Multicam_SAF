import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import os
import time
from urllib.parse import unquote

# async 사용
async def crawl_and_save_namuwiki_text(team_key, url):
    
    file_name = f"{team_key}_namuwiki_season.txt" 
    output_dir = "(KOR)F1_Crawled_Data"
    os.makedirs(output_dir, exist_ok=True) 

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            response = await page.goto(url)
            if response is None or response.status >= 400:
                print(f"❌ [{team_key}] HTTP 요청 실패: {response.status if response else 'N/A'}")
                return None
            
            # '개요' 섹션의 h2 태그가 나타날 때까지 기다린다.
            # 이 태그가 본문 로딩이 완료되었음을 나타내는 신호라고 가정한다.
            # state='attached' 옵션으로 팝업 등에 가려져도 존재 여부만 체크한다.
            await page.wait_for_selector('h2:has-text("개요")', state='attached', timeout=60000) 

            html_content = await page.content()
            await browser.close() 
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 핵심 콘텐츠 영역 선택 
            # (문서의 본문을 감싸는 가장 큰 DIV를 찾는다. ID가 없는 경우 role을 사용해 추정.)
            # HTML을 보면 문서 본문은 <div class="NMmqIPVM _61W7Avfw"> 안에 있다.
            # 하지만 이 클래스는 동적일 수 있으므로, 문서의 고유 ID가 없는 경우, 가장 큰 내용 컨테이너를 찾는다.
            # 여기서는 편의상 ID "app" 바로 안의 큰 DIV를 추적하는 것으로 가정한다.
            
            # 문서의 고유 ID를 가진 부모 DIV를 찾는다. ('content'의 부모)
            # 문서 내용이 있는 가장 큰 컨테이너를 찾아본다.
            # 테스트를 위해 '맥라렌 포뮬러 1 팀' 페이지에서 문서 내용이 시작되는 큰 div를 선택.
            # 여기서는 문서의 메인 영역인 <div class="NMmqIPVM _61W7Avfw">를 포함하는 부모 DIV를 사용한다.
            
            # 문서의 본문 영역이 시작되는 곳
            main_container = soup.find('div', class_='NMmqIPVM _61W7Avfw')
            if not main_container:
                # 만약 저 클래스마저 바뀌었다면, 문서 제목(h1)을 찾고 그 이후의 모든 콘텐츠를 대상으로 파싱할 수밖에 없음.
                # 그러나 여기서는 위에서 찾은 클래스를 유지하고, 만약 또 실패하면 Playwright의 로케이터 전략을 바꿔야 함.
                print(f"❌ [{team_key}] 문서의 메인 콘텐츠 DIV를 찾을 수 없습니다. (클래스가 변경되었을 수 있습니다.)")
                return None
            
            content = main_container
            
            # 노이즈(표, 각주, 이미지, 미디어) 제거 및 텍스트 추출
            for table in content.find_all('table'): table.decompose()
            for span in content.find_all('span', class_='wiki-fn-content'): span.decompose()
            for tag in content.find_all(['img', 'video', 'figure']): tag.decompose()
            
            extracted_text = []

            # select() 메서드를 사용하여 정확한 제목과 문단 태그를 추출
            # 나무위키는 주로 h2, h3, h4를 제목으로 사용
            elements_to_extract = content.select('h2, h3, h4, div.IBdgNaCn') # div.IBdgNaCn는 문단 텍스트를 포함하는 부모

            for element in elements_to_extract:
                tag_name = element.name
                text_content = element.text.strip()
                
                # '개요', '역사', '논란' 등의 제목만 처리
                if tag_name in ['h2', 'h3', 'h4']:
                    # 링크 제거
                    link_text = element.find('a', class_="zkdXfE03")
                    if link_text:
                        # 제목 텍스트에서 링크된 부분을 제거
                        link_text.decompose() 
                    
                    header_text = element.text.strip()
                    if "개요" in header_text or "역사" in header_text or "논란" in header_text or "여담" in header_text:
                        extracted_text.append(f"\n[{tag_name.upper()}] {header_text}")
                
                # 문단 텍스트만 추출 (IBdgNaCn 클래스 DIV 내부의 순수한 텍스트만)
                elif tag_name == 'div' and 'IBdgNaCn' in element.get('class', []):
                    # 불필요한 각주 링크도 제거 (위에서 이미 처리했으나, 중복 적용으로 안정화)
                    for link in element.find_all('a', class_='i626Z3U1'):
                         link.decompose()
                    
                    paragraph_text = element.text.strip()
                    # 너무 짧은 텍스트(예: 빈 줄)와 표 내용이 잔재로 남는 것을 필터링
                    if paragraph_text and len(paragraph_text) > 10:
                        extracted_text.append(paragraph_text)


            # 결과를 TXT 파일로 저장
            full_path = os.path.join(output_dir, file_name)

            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(f"URL: {url}\n\n")
                f.write(f"팀 이름: {unquote(url.split('/')[-1])} \n") 
                f.write("========== TEAM NARRATIVE DATA (Namuwiki) ==========\n")
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
namuwiki_team = {
    "Scuderia_Ferrari": "https://namu.wiki/w/%EC%8A%A4%EC%BF%A0%EB%8D%B0%EB%A6%AC%EC%95%84%20%ED%8E%98%EB%9D%BC%EB%A6%AC%20HP",
    "Red_Bull_Racing": "https://namu.wiki/w/%EC%98%A4%EB%9D%BC%ED%81%B4%20%EB%A0%88%EB%93%9C%EB%B6%88%20%EB%A0%88%EC%9D%B4%EC%8B%B1",
    "McLaren": "https://namu.wiki/w/%EB%A7%A5%EB%9D%BC%EB%A0%8C%20%ED%8F%AC%EB%AE%AC%EB%9F%AC%201%20%ED%8C%80",
    "Alpine_F1_Team": "https://namu.wiki/w/BWT%20%EC%95%8C%ED%95%80%20%ED%8F%AC%EB%AE%AC%EB%9F%AC%20%EC%9B%90%20%ED%8C%80",
    "Haas_F1_Team": "https://namu.wiki/w/%EB%A8%B8%EB%8B%88%EA%B7%B8%EB%9E%A8%20%ED%95%98%EC%8A%A4%20F1%20%ED%8C%80",
    "Sauber_Motorsport": "https://namu.wiki/w/%EC%8A%A4%ED%85%8C%EC%9D%B4%ED%81%AC%20F1%20%ED%8C%80%20%ED%82%A5%20%EC%9E%90%EC%9A%B0%EB%B2%84",
    "Aston_Martin_in_Formula_One": "https://namu.wiki/w/%EC%95%A0%EC%8A%A4%ED%84%B4%20%EB%A7%88%ED%8B%B4%20%EC%95%84%EB%9E%8C%EC%BD%94%20%ED%8F%AC%EB%AE%AC%EB%9F%AC%20%EC%9B%90%20%ED%8C%80",
    "Mercedes-Benz_in_Formula_One": "https://namu.wiki/w/%EB%A9%94%EB%A5%B4%EC%84%B8%EB%8D%B0%EC%8A%A4-AMG%20%ED%8E%98%ED%8A%B8%EB%A1%9C%EB%82%98%EC%8A%A4%20%ED%8F%AC%EB%AE%AC%EB%9F%AC%20%EC%9B%90%20%ED%8C%80",
    "Williams_Racing": "https://namu.wiki/w/%EC%95%84%ED%8B%80%EB%9D%BC%EC%8B%9C%EC%95%88%20%EC%9C%8C%EB%A6%AC%EC%97%84%EC%8A%A4%20%EB%A0%88%EC%9D%B4%EC%8B%B1",
    "Racing_Bulls": "https://namu.wiki/w/%EB%B9%84%EC%9E%90%20%EC%BA%90%EC%8B%9C%20%EC%95%B1%20%EB%A0%88%EC%9D%B4%EC%8B%B1%20%EB%B6%88%EC%8A%A4%20%ED%8F%AC%EB%AE%AC%EB%9F%AC%20%EC%9B%90%20%ED%8C%80"
}

# Playwright는 비동기 환경에서 실행해야 함
async def main_async():
    print("나무위키 F1 팀 데이터 크롤링을 시작합니다...\n")

    tasks = []
    for team_key, url in namuwiki_team.items():
        # 각 팀에 대한 크롤링 작업을 tasks 리스트에 담는다.
        tasks.append(crawl_and_save_namuwiki_text_async(team_key, url))
        
    # 핵심: asyncio.gather를 await로 실행!
    # 이 부분이 비동기(async) 함수 내부에서 실행되어야 한다.
    await asyncio.gather(*tasks) 
    
    print("\n모든 팀에 대한 크롤링 작업이 완료되었습니다.")

if __name__ == "__main__":
    # asyncio.run()은 최상위 비동기 함수(main_async)만 실행한다.
    asyncio.run(main_async())