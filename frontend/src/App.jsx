import { useRef } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext.jsx';
import Navbar from './components/Navbar.jsx';
import ScrollToTop from './components/ScrollToTop.jsx';
import Footer from './components/Footer.jsx';
import HomePage from './pages/HomePage.jsx';
import DesignPage from './pages/DesignPage/index.jsx';
import ResultsPage from './pages/ResultsPage/index.jsx';
import AnalyzePage from './pages/AnalyzePage/index.jsx';
import HistoryPage from './pages/HistoryPage/index.jsx';
import BenchmarkPage from './pages/BenchmarkPage.jsx';
import NotFoundPage from './pages/NotFoundPage.jsx';

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
          <main ref={mainRef} className="flex-1 overflow-y-auto px-4 py-5 sm:p-6">
            <Routes>
              <Route path="/" element={<Navigate to="/design" replace />} />
              <Route path="/home" element={<HomePage />} />
              {/* One designer: miRNA first, every parameter folded under "Parameters". */}
              <Route path="/design" element={<DesignPage />} />
              {/* Former Basic/Advanced split — old links and bookmarks land on the designer. */}
              <Route path="/design/advanced" element={<Navigate to="/design" replace />} />
              {/* Legacy route — keeps older links and bookmarks working. */}
              <Route path="/search" element={<Navigate to="/design" replace />} />
              <Route path="/analyze" element={<AnalyzePage />} />
              <Route path="/results" element={<ResultsPage />} />
              <Route path="/benchmark" element={<BenchmarkPage />} />
              <Route path="/history" element={<HistoryPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </main>
        </div>
        <Footer />
      </div>
    </ThemeProvider>
  );
}
