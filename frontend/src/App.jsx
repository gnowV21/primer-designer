import { Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext.jsx';
import Navbar from './components/Navbar.jsx';
import Footer from './components/Footer.jsx';
import ChatbotPanel from './components/ChatbotPanel.jsx';
import HomePage from './pages/HomePage.jsx';
import RoadmapPage from './pages/RoadmapPage.jsx';
import SearchPage from './pages/SearchPage/index.jsx';
import ResultsPage from './pages/ResultsPage/index.jsx';

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
              <Route path="/roadmap" element={<RoadmapPage />} />
              <Route path="/search" element={<SearchPage />} />
              <Route path="/results" element={<ResultsPage />} />
            </Routes>
          </main>
          <ChatbotPanel />
        </div>
        <Footer />
      </div>
    </ThemeProvider>
  );
}
