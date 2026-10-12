# 한국어 영화 추천 (백엔드 + 웹 화면)

한국어 영화 리뷰 26,768건(영화 214편)으로 영화를 추천하는 프로젝트입니다.
리뷰 글 유사도, 영화 정보(장르·등급·관객 수 등), 리뷰 수를 반영한 보정 평점을 합쳐 추천하는 **콘텐츠 기반 추천 FastAPI 백엔드**와, 그 위의 **React 화면**으로 이루어져 있습니다.

제공 기능: 검색(자동완성), 영화 상세(평점 분포·대표 키워드·리뷰), 추천(추천 근거 표시), 취향 추천(영화 2~5편 선택), 영화 비교, 전체 영화 둘러보기, 통계.
기존 평점 예측 실험(TF-IDF + Ridge)은 이 문서 아래쪽과 `archive/`에 보존했고 현재 서비스에는 필요하지 않습니다.

## 빠르게 실행 (Windows)

준비물: Python 3.12, 원본 데이터 `Koreanmovie_review.csv`(저장소에 없음, 아래 "데이터 준비"), 화면까지 보려면 Node.js LTS.

**1. 처음 한 번 (PowerShell, 프로젝트 폴더에서)**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
python clean_reviews.py                             # 글자가 지워진/너무 짧은 리뷰를 정리해 Koreanmovie_review_cleaned.csv 생성
.\.venv\Scripts\python.exe run_pipeline.py --input Koreanmovie_review_cleaned.csv   # 추천 데이터 준비 (artifacts/에 저장)
cd frontend
npm.cmd ci --ignore-scripts                         # React 화면용 (선택). npm이 막히면 npm.cmd를 씁니다
cd ..
```

**2. 실행**: 탐색기에서 **`run.bat`을 더블클릭**하면 백엔드(8000)와 화면(5173)이 함께 켜지고 브라우저가 열립니다. 끌 때는 **`stop.bat`**.
Node.js가 없으면 백엔드만 켜고 `http://127.0.0.1:8000/`의 간단한 단일 HTML 화면을 엽니다. PowerShell에서 직접 실행할 때는 `.\run.bat`처럼 `.\`를 붙입니다.

| 주소 | 내용 |
|---|---|
| `http://127.0.0.1:5173` | React 화면 |
| `http://127.0.0.1:8000/` | 단일 HTML 화면(Node 없이 확인용) |
| `http://127.0.0.1:8000/docs` | API 시험 화면(Swagger) |

수동 실행: `.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000`, 화면은 `frontend`에서 `npm.cmd run dev -- --host 127.0.0.1`.

**3. 테스트**

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt   # pytest (한 번만)
.\.venv\Scripts\python.exe -m pytest                                # 백엔드 104개
cd frontend; npm.cmd test; npm.cmd run lint                         # 프론트 16개 + 린트
```

> 문서의 `C:\Users\PC_1M\Documents\moive` 같은 경로 예시는 작성한 PC 기준입니다. 본인 프로젝트 폴더로 바꿔 읽으세요.
> `.venv`는 다른 PC로 복사하지 말고 새로 만드세요.

## 문서 안내

| 읽는 사람 | 문서 |
|---|---|
| 처음 보는 팀원 | 이 README → [현재 상태](docs/CURRENT_STATUS.md) |
| 프론트 담당 | [프론트 변경 요약](docs/FRONTEND_CHANGES.md)(팀원 원본과의 차이, 합칠 때 확인할 것) → [API 응답 구조](docs/API_RESPONSES.md) |
| 백엔드·데이터 담당 | [백엔드 안내](docs/BACKEND_GUIDE.md)(데이터 흐름, 점수 계산, 라이브러리 선택 이유) → [함수 목록](docs/FUNCTIONS.md) |
| 추천 품질 | [추천 설정 비교 보고서](docs/RECOMMENDATION_EVALUATION.md)와 사람 평가 시트(`docs/human_eval/`) |
| 배포 | [Docker 안내](docs/DOCKER.md) |
| 팀원 저장소와 합치기 | [합치는 방법](docs/MERGE_GUIDE.md)(달라진 파일 목록, 압축 파일에서 복사하면 안 되는 것, 명령 예시) |
| 이력서·발표 | [포트폴리오용 요약](docs/PORTFOLIO_SUMMARY.md)(쓸 수 있는 표현과 아직 쓰면 안 되는 표현) |
| 기록 | [환경 변경 기록](docs/ENVIRONMENT_CHANGES.md)(이 PC 전용), [10월 1일 인계 원문](docs/HANDOFF_2026-10-01.md), [파일 정리 안내](docs/FILE_ORGANIZATION.md), [프로젝트_실행방법.txt](프로젝트_실행방법.txt) |

## 현재 상태 (2026-10-11)

- **확인함:** 백엔드 16개 API, React 화면, 백엔드 테스트 104개와 프론트 테스트 16개 통과, 실제 데이터로 화면·API 동작 확인.
- **작성만 하고 실행해 보지 못함:** Docker(`Dockerfile`, `docker-compose.yml`), GitHub Actions(`.github/workflows/test.yml`).
- **아직 안 함:** 추천 결과의 사람 평가(시트만 준비됨), 팀원 저장소와 합치기, React를 FastAPI가 같이 서빙하는 한 서버 구조.
- **알려진 한계:** 영화 214편·장르 3개, 대표 키워드는 형태소 분석 없이 규칙으로 만들어 의미 없는 단어가 일부 섞임.

## 기존 평점 예측 실험

코드와 기존 CSV 결과는 `archive/rating_prediction`으로 모았습니다. 이 실험은 현재 추천 서버 실행에 필요하지 않습니다.
정리된 폴더별 역할과 유지할 파일은 [파일 정리 안내](docs/FILE_ORGANIZATION.md)를 참고하세요.

리뷰 글로 작성자가 준 실제 평점(0.5~5.0)을 예측하는 교육용 프로젝트입니다.
TF-IDF + Ridge부터 이해하고 이후 LSTM과 비교하는 것이 목표입니다.

## 데이터 준비
출처: https://www.kaggle.com/datasets/suminwang/korean-movie-review-data-30kbert
폴더명은 NSMC지만 표준 NSMC 이진 감성 데이터가 아닙니다.
원본을 다운로드하거나 기존 PC에서 복사해 이 폴더에 `Koreanmovie_review.csv`로 둡니다.
CSV는 저장소에 포함하지 않습니다. 데이터 재배포 조건은 별도로 확인해야 합니다.
`bert_label`, `neg_score`, `pos_score`는 기존 모델 예측이므로 정답으로 사용하지 않습니다.

## 새 PC에서 실행 (Windows PowerShell)
```powershell
git clone https://github.com/JungUH-0/JungPra.git
cd JungPra/pythonpra/NSMC
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe archive\rating_prediction\datachk.py
.\.venv\Scripts\python.exe archive\rating_prediction\split_data.py
.\.venv\Scripts\python.exe archive\rating_prediction\train_model.py
```
`datachk.py`는 프로젝트 루트의 원본을 읽고 정리 CSV를 `archive/rating_prediction`에 저장합니다.
기존 실행은 Python 3.14에서 이루어졌습니다. 패키지 버전은 아직 고정하지 않았으므로 환경에 따라 결과가 달라질 수 있습니다.

## 실행 흐름
1. `datachk.py`: 리뷰/평점 결측, 빈 리뷰와 완전 중복을 제거하고 clean/ready CSV를 저장합니다.
2. `split_data.py`: 같은 리뷰 문구가 양쪽에 들어가지 않도록 분리해 train/test CSV를 저장합니다.
3. `train_model.py`: 학습용에만 TF-IDF를 fit하고 Ridge를 학습해 predictions CSV를 저장합니다.
재실행하면 해당 출력 CSV를 덮어씁니다. 입력 원본은 수정하지 않습니다.

## 확인된 결과
- ready 26,321행, train 21,052행, test 5,269행, 양쪽 리뷰 교집합 0.
- 학습 행렬 (21052, 50000), 평가 행렬 (5269, 50000).
- 사용자 실행 결과: 평균 평점 기준 MAE 0.8913점, Ridge MAE 0.7464점.
- MAE는 평균 절대 오차이며 정확도 퍼센트가 아닙니다.
- 모델 설정: 문자 1~3그램, min_df=3, max_features=50000, sublinear_tf=True, Ridge alpha=10, solver=lsqr.
- predictions CSV: review, rating, predicted_rating, absolute_error.

## 평가의 한계
영화 단위 분리가 아니므로 새로운 영화에 대한 일반화 평가로 해석하지 않습니다.
플랫폼별 평점 척도 통일 여부는 미검증입니다.
튜닝은 기존 학습용 내부에서 리뷰 문구 기준으로 나눈 검증용 데이터로 진행합니다.
평가용은 설정을 선택하는 데 반복 사용하지 않습니다.

최신 진행 상황은 `docs/CURRENT_STATUS.md`, 과거 인계 기록은 `docs/HANDOFF_2026-10-01.md`를 참고하세요.
