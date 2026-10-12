import './App.css'
import ErrorBoundary from './components/ErrorBoundary'
import { useHashRoute } from './hooks/useHashRoute'
import { useMovieSearch } from './hooks/useMovieSearch'
import BrowsePage from './pages/BrowsePage'
import ComparePage from './pages/ComparePage'
import HomePage from './pages/HomePage'
import KeywordPage from './pages/KeywordPage'
import MovieDetailPage from './pages/MovieDetailPage'
import TastePage from './pages/TastePage'

const NAV = [
  ['home', '#/', '홈'],
  ['browse', '#/browse', '전체 영화'],
  ['taste', '#/taste', '취향 추천'],
]

function App() {
  const route = useHashRoute()
  const search = useMovieSearch()

  return (
    <div className="app">
      <header className="header">
        <a className="logo" href="#/">🎬 Korean Movie</a>
        <nav className="nav" aria-label="주요 메뉴">
          {NAV.map(([name, href, label]) => (
            <a key={name} href={href} className={route.name === name ? 'active' : undefined}>{label}</a>
          ))}
        </nav>
      </header>

      <main className="main">
        {/* 주소가 바뀌면 key가 달라져 오류 상태가 풀린다 */}
        <ErrorBoundary key={window.location.hash}>
        {route.name === 'movie' && (
          // key가 바뀌면 화면이 새로 만들어져 이전 영화의 상태가 남지 않는다.
          <MovieDetailPage key={route.movieId} movieId={route.movieId} />
        )}
        {route.name === 'browse' && <BrowsePage query={route.query} />}
        {route.name === 'taste' && <TastePage />}
        {route.name === 'keyword' && <KeywordPage key={route.term} term={route.term} />}
        {route.name === 'compare' && <ComparePage key={`${route.a}|${route.b}`} a={route.a} b={route.b} />}
        {route.name === 'home' && <HomePage search={search} />}
        </ErrorBoundary>
      </main>
    </div>
  )
}

export default App
