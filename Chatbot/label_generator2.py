import json
import pandas as pd
import numpy as np
import os
from sentence_transformers import SentenceTransformer
from node2vec import Node2Vec
import networkx as nx
from sklearn.metrics.pairwise import cosine_similarity

# ---------------------------------------------------------
# 1. 초기 설정 및 가중치 (최종 튜닝)
# ---------------------------------------------------------
ALPHA = 0.7  # Semantic (의미적 유사도)
BETA = 0.3   # Relational (관계적 유사도 - Anchor Team 기준)
DATA_DIR = r'./' # 실제 JSON 폴더 경로

# 모델 로드 (한국어 특화 모델)
model_nlp = SentenceTransformer('snunlp/KR-SBERT-V40K-klueNLI-augSTS')

# ---------------------------------------------------------
# 2. 데이터 로드 및 관계망 학습
# ---------------------------------------------------------
def load_teams(path):
    teams = []
    if os.path.exists(path):
        for filename in os.listdir(path):
            if filename.endswith('.json'):
                with open(os.path.join(path, filename), 'r', encoding='utf-8') as f:
                    teams.append(json.load(f))
        print(f"✅ 총 {len(teams)}개의 팀 데이터를 로드했습니다.")
    return teams

def train_node2vec(data):
    G = nx.Graph()
    for i in range(len(data)):
        for j in range(i + 1, len(data)):
            # 한글 태그 기반 관계망 형성
            common_tags = set(data[i].get('style_tags', [])) & set(data[j].get('style_tags', []))
            if common_tags:
                G.add_edge(data[i]['team_name'], data[j]['team_name'], weight=len(common_tags))
    if len(G.nodes) == 0: return None
    node2vec = Node2Vec(G, dimensions=64, walk_length=10, num_walks=40, workers=1)
    return node2vec.fit(window=5, min_count=1)

teams_data = load_teams(DATA_DIR)
print("⚙️ 관계망(Node2Vec) 학습 중...")
n2v_model = train_node2vec(teams_data)

# ---------------------------------------------------------
# 3. 고도화된 통합 점수 계산 함수 (버그 수정 포함)
# ---------------------------------------------------------
def calculate_integrated_score(anchor_team, user_query, candidate_team, n2v_model):
    cand_name = candidate_team['team_name']

    # [수정 1] 이름 불일치 해결 (Partial Match)
    # anchor가 "토트넘"이어도 "토트넘 홋스퍼"를 본인으로 인식하도록 개선
    if anchor_team and anchor_team != "None":
        if anchor_team in cand_name or cand_name in anchor_team:
            return 0.0 # 본인 팀은 추천에서 즉시 제외

    # (1) S_semantic: NLP 의미 분석
    team_tags_str = " ".join(candidate_team.get('style_tags', []))
    embeddings = model_nlp.encode([user_query, team_tags_str])
    s_semantic = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]

    # (2) S_relational: 응원팀과의 그래프 거리
    s_relational = 0.5 
    if anchor_team and anchor_team != "None":
        try:
            s_relational = n2v_model.wv.similarity(anchor_team, cand_name)
        except:
            # 부분 일치하는 다른 이름으로 시도
            s_relational = 0.5

    # (3) W_identity: 질문 기반 정체성 가중치
    scores = candidate_team.get('scores', {})
    
    if any(k in user_query for k in ["자본", "돈", "부자"]): category = 'money'
    elif any(k in user_query for k in ["언더독", "기적", "약팀", "낭만"]): category = 'underdog_feel'
    elif any(k in user_query for k in ["역사", "전통", "명문"]): category = 'tradition'
    elif any(k in user_query for k in ["공격", "화끈"]): category = 'attack_style'
    elif any(k in user_query for k in ["스타", "개인", "선수"]): category = 'star_power'
    else: category = 'strength'

    raw_val = scores.get(category, 5) / 10
    identity_val = raw_val ** 2 
    w_identity = 0.7 + (identity_val * 0.6)

    # [수정 2] 언더독 질문의 논리 강화 (Hard-coded Penalty)
    # "언더독" 질문인데 자본력이 8점 이상인 부자 팀은 점수를 강제로 삭감
    penalty = 1.0
    if any(k in user_query for k in ["언더독", "기적", "약팀", "낭만"]):
        if scores.get('money', 0) >= 8:
            penalty = 0.4 # 부자 강팀 페널티

    # 최종 합산
    final_score = ((ALPHA * s_semantic) + (BETA * s_relational)) * w_identity * penalty
    return final_score

# ---------------------------------------------------------
# 4. 시나리오 실행 및 CSV 저장
# ---------------------------------------------------------
scenarios = [
    {"anchor": "None", "query": "해외 축구 입문자인데 성적 좋고 화려한 팀 추천해줘"},
    {"anchor": "아스널", "query": "아스널 팬인데 아스널처럼 패스 위주의 예쁜 축구를 하는 다른 팀이 궁금해"},
    {"anchor": "토트넘", "query": "토트넘 팬인데 이제 무관은 지겨워. 우승권인 팀으로 갈아탈래"},
    {"anchor": "맨체스터 시티", "query": "맨시티만큼 돈 걱정 없이 스타 선수들 모으는 팀 또 어디야?"},
    {"anchor": "None", "query": "돈으로 우승을 사는 팀은 싫어. 낭만 있는 언더독의 기적을 보고 싶어"},
    {"anchor": "리버풀", "query": "리버풀의 뜨거운 응원 문화가 좋아. 비슷한 열정을 가진 팀이 또 있어?"},
    {"anchor": "첼시", "query": "첼시 팬인데 요즘 너무 혼란스러워. 첼시처럼 부유하면서 운영은 안정적인 팀은?"},
    {"anchor": "None", "query": "전 세계 최고 스타들이 모인 화려한 팀이 어디인지 궁금해"},
    {"anchor": "아스톤 빌라", "query": "빌라처럼 전통이 깊으면서도 요즘 다시 부활하는 명문 팀 추천해줘"},
    {"anchor": "None", "query": "지역 주민들과 끈끈하고 역사적 깊이가 느껴지는 구단을 찾고 있어"}
]

dataset = []
print("\n📊 버그 수정 및 로직 강화 버전 데이터 생성 중...")

for scene in scenarios:
    anchor = scene['anchor']
    query = scene['query']
    for candidate in teams_data:
        score = calculate_integrated_score(anchor, query, candidate, n2v_model)
        dataset.append({
            'anchor_team': anchor,
            'user_query': query,
            'team_name': candidate['team_name'],
            'label_score': score
        })

df = pd.DataFrame(dataset)
df.to_csv('final_training_data_integrated_v2.csv', index=False, encoding='utf-8-sig')
print("\n✨ 최종 데이터 생성 완료! 'final_training_data_integrated_v2.csv'를 확인하세요.")