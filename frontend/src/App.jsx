import { useRef } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext.jsx';
import Navbar from './components/Navbar.jsx';
import ScrollToTop from './components/ScrollToTop.jsx';
import Footer from './components/Footer.jsx';
import HomePage from './pages/HomePage.jsx';
import BasicDesignPage from './pages/DesignPage/BasicDesignPage.jsx';
import SearchPage from './pages/SearchPage/index.jsx';
import ResultsPage from './pages/ResultsPage/index.jsx';
import AnalyzePage from './pages/AnalyzePage/index.jsx';
import HistoryPage from './pages/HistoryPage/index.jsx';
import BenchmarkPage from './pages/BenchmarkPage.jsx';

export default function App() {
  // <main> is the scroll container (the document itself never scrolls), so
  // ScrollToTop needs this ref to reset the offset on every navigation.
  const mainRef = useRef(null);

  return (
    <ThemeProvider>
      <div className="h-screen flex flex-col">
        <Navbar />
        <ScrollToTop containerRef={mainRef} />
        <div className="flex flex-row flex-1 min-h-0">
          <main ref={mainRef} className="flex-1 overflow-y-auto p-6">
            <Routes>
              <Route path="/" element={<Navigate to="/design" replace />} />
              <Route path="/home" element={<HomePage />} />
              {/* Basic is the default designer; Advanced exposes every parameter. */}
              <Route path="/design" element={<BasicDesignPage />} />
              <Route path="/design/advanced" element={<SearchPage />} />
              {/* Legacy route — keeps older links and bookmarks working. */}
              <Route path="/search" element={<Navigate to="/design" replace />} />
              <Route path="/analyze" element={<AnalyzePage />} />
              <Route path="/results" element={<ResultsPage />} />
              <Route path="/benchmark" element={<BenchmarkPage />} />
              <Route path="/history" element={<HistoryPage />} />
            </Routes>
          </main>
        </div>
        <Footer />
      </div>
    </ThemeProvider>
  );
}
