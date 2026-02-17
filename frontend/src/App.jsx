import { Navigate, Route, Routes } from 'react-router-dom'
import CommandCenter from './components/CommandCenter'
import AgentWorkspace from './components/AgentWorkspace'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<CommandCenter />} />
      <Route path="/agent/:agentId" element={<AgentWorkspace />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
