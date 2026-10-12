// 백엔드 주소. 다른 주소를 쓰려면 frontend/.env에 VITE_API_BASE_URL=http://... 을 적는다.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

// 백엔드 오류의 detail은 404=문자열, 409=객체, 422=배열이라 모양에 맞춰 문구를 만든다.
function errorMessage(status, detail) {
  if (status === 404) return '해당하는 영화를 찾을 수 없습니다.'
  if (status === 409) return detail?.message ?? '같은 제목의 영화가 여러 개입니다.'
  if (status === 422) return '입력값이 올바르지 않습니다.'
  return `요청을 처리하지 못했습니다. (${status})`
}

async function getJson(path, params = {}) {
  const query = new URLSearchParams(params).toString()
  let response
  try {
    response = await fetch(`${API_BASE_URL}${path}${query ? `?${query}` : ''}`)
  } catch {
    throw new Error('서버에 연결할 수 없습니다. 백엔드가 실행 중인지 확인하세요.')
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(errorMessage(response.status, body.detail))
  }
  return response.json()
}

// 영화 ID는 내부 값이라 URL 경로에 넣을 때 인코딩한다. ID 경로는 동명이작 409가 생기지 않는다.
const pathId = (movieId) => encodeURIComponent(movieId)

export function searchMovies(query, limit = 20) {
  return getJson('/movies', { query, limit })
}

export function getMovie(movieId) {
  return getJson(`/movies/${pathId(movieId)}`)
}

export function getRecommendations(movieId, topN = 6) {
  return getJson(`/recommend/${pathId(movieId)}`, { top_n: topN })
}

// order: 'high'(높은 평점순) | 'low'(낮은 평점순)
// keyword를 주면 그 글자가 들어 있는 리뷰만 가져온다.
export function getReviews(movieId, order = 'high', topN = 10, keyword = '') {
  const params = { order, top_n: topN }
  if (keyword) params.keyword = keyword
  return getJson(`/movies/${pathId(movieId)}/reviews`, params)
}

// 전체 통계: 영화/리뷰 수, 평점·장르 분포, 보정 평점 상위, 리뷰 많은 영화
export function getStatistics(topN = 6) {
  return getJson('/statistics', { top_n: topN })
}

// 리뷰에서 특징적으로 자주 나온 단어
export function getKeywords(movieId, topN = 12) {
  return getJson(`/movies/${pathId(movieId)}/keywords`, { top_n: topN })
}

// 전체 영화 둘러보기. sort: title|rating|reviews|newest, direction: asc|desc
export function browseMovies({ sort = 'rating', direction = 'desc', genre, director, offset = 0, limit = 24 } = {}) {
  const params = { sort, direction, offset, limit }
  if (genre) params.genre = genre
  if (director) params.director = director
  return getJson('/movies/browse', params)
}

// 좋아하는 영화 2~5편(ID)을 모두 반영한 추천
export function getTasteRecommendations(movieIds, topN = 8) {
  const params = new URLSearchParams({ top_n: topN })
  movieIds.forEach((id) => params.append('movie_ids', id))
  return getJson(`/recommend/taste?${params.toString()}`)
}

// 영화 두 편 비교
export function compareMovies(a, b) {
  return getJson('/compare', { a, b })
}

// 영화 한 편의 평점 분포 (0.5~5.0, 10칸)
export function getRatingDistribution(movieId) {
  return getJson(`/movies/${pathId(movieId)}/ratings`)
}

// 이 단어가 대표 키워드에 든 영화들(점수 순)
export function getMoviesByKeyword(term, limit = 24) {
  return getJson('/keywords/movies', { term, limit })
}
