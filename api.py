"""검색·추천·리뷰·통계·키워드·비교 조회를 연결하는 FastAPI 백엔드입니다.

React 프론트(frontend/)는 별도로 실행하며, 이 서버는 static/의 간단한 웹 화면(/)만 함께 제공합니다.

실행: python -m uvicorn api:app --host 127.0.0.1 --port 8000
먼저 python run_pipeline.py로 데이터를 준비해야 합니다.
"""

# contextlib: 서버 시작/종료 동작을 lifespan 함수로 묶기 위해 사용합니다.
from contextlib import asynccontextmanager
from pathlib import Path
# Literal: 리뷰 정렬 방향을 high/low 두 값으로 제한합니다.
from typing import Literal

# FastAPI: HTTP 요청을 파이썬 함수에 연결하고 요청 값의 범위도 검사합니다.
# FastAPI의 Path는 URL 경로 입력 설정입니다. pathlib.Path와 구분해 PathParameter로 이름을 붙입니다.
from fastapi import FastAPI, HTTPException, Path as PathParameter, Query, Request

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from pipeline_common import DEFAULT_ARTIFACTS, PROJECT_DIR
from data_store import load_data, search_movies, get_movie, find_movies_by_title
from recommender import recommend, recommend_for_taste
from review_service import get_reviews
from keyword_service import build_keywords, movies_by_keyword
from movie_statistics import build_statistics, movie_rating_distribution
from movie_browse import browse_movies
from movie_compare import compare_movies


STATIC_DIR = PROJECT_DIR / 'static'


def request_data(request):
    """서버 시작 때 한 번 읽은 데이터 딕셔너리를 현재 요청에 연결합니다."""
    return request.app.state.movie_data


def title_to_movie_id(data, title, release_date=None, director=None):
    """제목을 내부 영화 ID로 연결합니다. 없음=404, 동명이작=409와 후보 정보를 반환합니다."""
    try:
        candidates = find_movies_by_title(data, title, release_date, director)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not candidates:
        raise HTTPException(status_code=404, detail='조건에 맞는 영화 제목을 찾을 수 없습니다.')
    if len(candidates) > 1:
        raise HTTPException(status_code=409, detail={
            'message': '같은 제목의 작품이 여러 개입니다. release_date 또는 director를 추가하세요.',
            'candidates': candidates,
        })
    return candidates[0]['movie_id']


def movie_input_to_id(data, value):
    """기존 경로에 영화 ID 또는 정확한 제목을 넣을 수 있도록 입력값을 연결합니다."""
    if value in data['id_to_index']:
        return value
    return title_to_movie_id(data, value)


def recommendation_response(data, movie_id, top_n):
    """제목 요청/ID 요청이 동일한 추천 함수와 응답 구조를 사용하도록 묶습니다."""
    source = get_movie(data, movie_id)
    rows = recommend(data, movie_id, top_n)
    message = '장르 정보가 없어 추천 후보를 만들 수 없습니다.' if source['genre'] is None else None
    return {'source': source, 'count': len(rows), 'items': rows, 'message': message, 'data_version': data['manifest']['data_version']}


def keywords_response(request, data, movie_id, top_n):
    """시작 때 계산해 둔 키워드에서 한 영화의 상위 top_n개를 꺼냅니다."""
    movie = get_movie(data, movie_id)
    items = request.app.state.keywords.get(movie_id, [])[:top_n]
    return {'movie_id': movie_id, 'title': movie['title'], 'count': len(items), 'items': items}


def create_app(artifacts_dir=DEFAULT_ARTIFACTS):
    """저장 폴더를 받는 API 생성 함수입니다. 테스트에서는 임시 폴더를 전달합니다."""
    artifacts_dir = Path(artifacts_dir)

    @asynccontextmanager
    async def lifespan(application):
        """서버 시작 때 정상 버전을 한 번 로딩합니다. 요청마다 학습/계산하지 않습니다."""
        application.state.movie_data = load_data(artifacts_dir)
        # 키워드는 서버 시작 때 한 번 계산합니다. 요청마다 TF-IDF를 계산하지 않습니다.
        application.state.keywords = build_keywords(application.state.movie_data['profiles'])
        yield
        # 파일은 로딩 시 이미 닫혔습니다. 종료 때 메모리 참조를 정리합니다.
        application.state.movie_data = None
        application.state.keywords = None

    application = FastAPI(title='영화 추천 백엔드', version='1.1.0', lifespan=lifespan)

    # React 개발 서버(Vite, 5173)가 브라우저에서 이 API를 호출할 수 있도록 허용합니다.
    # 읽기 전용 GET만 열고, 이 PC의 개발 주소만 허용합니다.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
        allow_methods=['GET'],
        allow_headers=[],
    )

    # 간단한 웹 화면(static/index.html). 같은 서버에서 제공하므로 CORS 설정이 필요 없습니다.
    if STATIC_DIR.is_dir():
        application.mount('/app', StaticFiles(directory=STATIC_DIR, html=True), name='web')

        @application.get('/', include_in_schema=False)
        def home():
            """접속 주소(/)로 들어오면 웹 화면으로 이동시킵니다."""
            return RedirectResponse('/app/')

    @application.get('/health')
    def health(request: Request):
        """현재 데이터 버전과 준비된 영화/리뷰 개수를 반환합니다."""
        data = request_data(request)
        return {'status': 'ok', 'data_version': data['manifest']['data_version'], 'movies': len(data['profiles']), 'reviews': len(data['reviews'])}

    @application.get('/movies')
    def movies(request: Request, query: str = Query(default='', max_length=200), limit: int = Query(default=20, ge=1, le=100)):
        """제목 일부로 검색합니다. 정확한 제목으로도 상세/추천/리뷰를 바로 조회할 수 있습니다."""
        rows = search_movies(request_data(request), query, limit)
        return {'count': len(rows), 'items': rows}

    @application.get('/statistics')
    def statistics(request: Request, top_n: int = Query(default=10, ge=1, le=20)):
        """전체 영화/리뷰 수, 평점 분포, 장르 분포, 보정 평점 상위·리뷰 많은 영화를 반환합니다."""
        return build_statistics(request_data(request), top_n)

    @application.get('/movies/browse')
    def movies_browse(
        request: Request,
        sort: Literal['title', 'rating', 'reviews', 'newest'] = Query(default='rating', description='rating=보정 평점, reviews=리뷰 수, newest=개봉일, title=제목'),
        direction: Literal['asc', 'desc'] = 'desc',
        genre: str | None = Query(default=None, min_length=1, max_length=50, description='정확한 장르 이름. 예: 드라마'),
        director: str | None = Query(default=None, min_length=1, max_length=200, description='정확한 감독 이름'),
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=24, ge=1, le=100),
    ):
        """검색어 없이 전체 영화를 정렬·장르 필터·페이지로 조회합니다. total은 필터 후 전체 개수입니다."""
        return browse_movies(request_data(request), sort, direction, genre, offset, limit, director)

    @application.get('/compare', responses={404: {'description': '영화 없음'}, 422: {'description': '같은 영화 또는 잘못된 입력'}})
    def compare(
        request: Request,
        a: str = Query(min_length=1, max_length=200, description='첫 번째 영화 ID 또는 정확한 제목'),
        b: str = Query(min_length=1, max_length=200, description='두 번째 영화 ID 또는 정확한 제목'),
    ):
        """영화 두 편의 정보, 유사도 구성(메타·리뷰·감독), 대표 키워드의 겹침을 비교합니다."""
        data = request_data(request)
        try:
            return compare_movies(data, movie_input_to_id(data, a), movie_input_to_id(data, b), request.app.state.keywords)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @application.get('/keywords/movies')
    def movies_with_keyword(
        request: Request,
        term: str = Query(min_length=1, max_length=50, description='찾을 키워드(정확히 일치). 영화의 대표 키워드 목록에서 얻은 값'),
        limit: int = Query(default=12, ge=1, le=50),
    ):
        """이 단어가 대표 키워드에 든 영화를 점수가 높은 순으로 반환합니다. 일치하는 영화가 없으면 빈 목록(200)입니다."""
        data = request_data(request)
        found = movies_by_keyword(request.app.state.keywords, term, limit)
        items = [{**get_movie(data, movie_id), 'keyword_score': score} for movie_id, score in found]
        return {'term': term.strip(), 'count': len(items), 'items': items}

    @application.get('/keywords', tags=['제목으로 조회'], responses={404: {'description': '제목 없음'}, 409: {'description': '동명이작: 후보 선택 필요'}})
    def keywords_by_title(
        request: Request,
        title: str = Query(min_length=1, max_length=200, description='정확한 영화 제목. 예: 승부'),
        top_n: int = Query(default=10, ge=1, le=30),
        release_date: str | None = Query(default=None, pattern=r'^\d{8}$'),
        director: str | None = Query(default=None, min_length=1, max_length=200),
    ):
        """영화 제목으로 리뷰에서 특징적으로 자주 나온 단어를 조회합니다."""
        data = request_data(request)
        movie_id = title_to_movie_id(data, title, release_date, director)
        return keywords_response(request, data, movie_id, top_n)

    # 고정 경로를 /movies/{movie_id}보다 먼저 등록해야 'detail'이 영화 ID로 해석되지 않습니다.
    @application.get('/movies/detail', tags=['제목으로 조회'], responses={404: {'description': '제목 없음'}, 409: {'description': '동명이작: 후보 선택 필요'}})
    def movie_detail_by_title(
        request: Request,
        title: str = Query(min_length=1, max_length=200, description='정확한 영화 제목. 예: 승부'),
        release_date: str | None = Query(default=None, pattern=r'^\d{8}$', description='동명이작 구분용 개봉일 YYYYMMDD'),
        director: str | None = Query(default=None, min_length=1, max_length=200, description='동명이작 구분용 감독'),
    ):
        """제목만으로 영화 상세를 조회합니다. 제목이 중복되면 개봉일/감독으로 구분하세요."""
        data = request_data(request)
        movie_id = title_to_movie_id(data, title, release_date, director)
        return get_movie(data, movie_id)

    @application.get('/recommend', tags=['제목으로 조회'], responses={404: {'description': '제목 없음'}, 409: {'description': '동명이작: 후보 선택 필요'}})
    def recommendations_by_title(
        request: Request,
        title: str = Query(min_length=1, max_length=200, description='정확한 영화 제목. 예: 승부'),
        top_n: int = Query(default=5, ge=1, le=20),
        release_date: str | None = Query(default=None, pattern=r'^\d{8}$'),
        director: str | None = Query(default=None, min_length=1, max_length=200),
    ):
        """입력한 영화 제목의 추천을 바로 반환합니다. ID 복사 단계가 필요하지 않습니다."""
        data = request_data(request)
        movie_id = title_to_movie_id(data, title, release_date, director)
        return recommendation_response(data, movie_id, top_n)

    @application.get('/movies/reviews', tags=['제목으로 조회'], responses={404: {'description': '제목 없음'}, 409: {'description': '동명이작: 후보 선택 필요'}})
    def reviews_by_title(
        request: Request,
        title: str = Query(min_length=1, max_length=200, description='정확한 영화 제목. 예: 서울의 봄'),
        order: Literal['high', 'low'] = 'high',
        top_n: int = Query(default=5, ge=1, le=20),
        release_date: str | None = Query(default=None, pattern=r'^\d{8}$'),
        director: str | None = Query(default=None, min_length=1, max_length=200),
        keyword: str | None = Query(default=None, max_length=50, description='이 글자가 들어 있는 리뷰만 조회'),
    ):
        """영화 제목으로 실제 평점순 리뷰를 조회합니다. high/low 방향을 선택할 수 있습니다."""
        data = request_data(request)
        movie_id = title_to_movie_id(data, title, release_date, director)
        rows = get_reviews(data, movie_id, top_n, order, keyword)
        return {'movie_id': movie_id, 'title': get_movie(data, movie_id)['title'], 'order': order, 'count': len(rows), 'items': rows}

    @application.get('/movies/{movie_id}')
    def movie_detail(request: Request, movie_id: str = PathParameter(min_length=1, max_length=200, description='영화 ID 또는 정확한 제목. 예: 승부')):
        """경로에 영화 ID 또는 제목을 넣어 메타데이터, 평균/보정 평점, 리뷰 수를 조회합니다."""
        data = request_data(request)
        selected_id = movie_input_to_id(data, movie_id)
        return get_movie(data, selected_id)

    @application.get('/recommend/taste', responses={404: {'description': '영화 ID 없음'}, 422: {'description': '영화 2~5편이 아님'}})
    def recommendations_by_taste(
        request: Request,
        movie_ids: list[str] = Query(min_length=2, max_length=5, description='좋아하는 영화의 ID를 2~5개. movie_ids=a&movie_ids=b 형태'),
        top_n: int = Query(default=5, ge=1, le=20),
    ):
        """고른 영화들을 모두 반영해 추천합니다. 후보의 유사도는 선택한 각 영화와의 평균입니다."""
        data = request_data(request)
        try:
            rows = recommend_for_taste(data, movie_ids, top_n)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc.args[0]))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        seeds = [get_movie(data, movie_id) for movie_id in dict.fromkeys(movie_ids)]
        return {'seeds': seeds, 'count': len(rows), 'items': rows, 'data_version': data['manifest']['data_version']}

    @application.get('/recommend/{movie_id}')
    def recommendations(request: Request, movie_id: str = PathParameter(min_length=1, max_length=200, description='영화 ID 또는 정확한 제목. 예: 승부'), top_n: int = Query(default=5, ge=1, le=20)):
        """경로의 영화 ID 또는 제목을 받아 같은 장르의 추천과 점수/근거를 반환합니다."""
        data = request_data(request)
        selected_id = movie_input_to_id(data, movie_id)
        return recommendation_response(data, selected_id, top_n)

    @application.get('/movies/{movie_id}/keywords')
    def keywords(request: Request, movie_id: str = PathParameter(min_length=1, max_length=200, description='영화 ID 또는 정확한 제목.'), top_n: int = Query(default=10, ge=1, le=30)):
        """경로의 영화 ID 또는 제목으로 대표 키워드를 조회합니다."""
        data = request_data(request)
        return keywords_response(request, data, movie_input_to_id(data, movie_id), top_n)

    @application.get('/movies/{movie_id}/ratings')
    def ratings(request: Request, movie_id: str = PathParameter(min_length=1, max_length=200, description='영화 ID 또는 정확한 제목.')):
        """영화 한 편의 평점 분포(0.5~5.0, 10칸)를 반환합니다. 평점이 있는 리뷰만 셉니다."""
        data = request_data(request)
        return movie_rating_distribution(data, movie_input_to_id(data, movie_id))

    @application.get('/movies/{movie_id}/reviews')
    def reviews(request: Request, movie_id: str = PathParameter(min_length=1, max_length=200, description='영화 ID 또는 정확한 제목. 예: 서울의 봄'), order: Literal['high', 'low'] = 'high', top_n: int = Query(default=5, ge=1, le=20), keyword: str | None = Query(default=None, max_length=50, description='이 글자가 들어 있는 리뷰만 조회')):
        """경로의 영화 ID 또는 제목으로 실제 평점순 리뷰를 조회합니다."""
        data = request_data(request)
        selected_id = movie_input_to_id(data, movie_id)
        rows = get_reviews(data, selected_id, top_n, order, keyword)
        return {'movie_id': selected_id, 'order': order, 'count': len(rows), 'items': rows}

    return application


# 앱 객체만 생성합니다. CSV/유사도 로딩은 서버 시작(lifespan)에서 실행됩니다.
app = create_app()
