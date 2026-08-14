import { Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext.jsx';
import Navbar from './components/Navbar.jsx';
import Footer from './components/Footer.jsx';
import HomePage from './pages/HomePage.jsx';
import SearchPage from './pages/SearchPage/index.jsx';
import ResultsPage from './pages/ResultsPage/index.jsx';
import BenchmarkPage from './pages/BenchmarkPage.jsx';

export default function App() {
  return (
    <ThemeProvider>
      <div className="h-screen flex flex-col">
        <Navbar />
        <div className="flex flex-row flex-1 min-h-0">
          <main className="flex-1 overflow-y-auto p-6">
            <Routes>
              <Route path="/" element={<Navigate to="/search" replace />} />
              <Route path="/home" element={<HomePage />} />
              <Route path="/search" element={<SearchPage />} />
              <Route path="/results" element={<ResultsPage />} />
              <Route path="/benchmark" element={<BenchmarkPage />} />
            </Routes>
          </main>
        </div>
        <Footer />
      </div>
    </ThemeProvider>
  );
}
