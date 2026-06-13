import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import About from './pages/About'
import Dashboard from './pages/Dashboard'
import Cases from './pages/Cases'
import EvidenceList from './pages/EvidenceList'
import EvidenceDetail from './pages/EvidenceDetail'
import AuditLog from './pages/AuditLog'
import { AttestationsList, AttestationDetail } from './pages/Attestations'
import Derived from './pages/Derived'
import Portal from './pages/Portal'
import InferenceProofView from './pages/InferenceProofView'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        {/* Landing for newcomers — explains AIP, no backend assumed. */}
        <Route index element={<About />} />
        <Route path="about" element={<About />} />

        {/* Operator-side dashboard (was previously at index). */}
        <Route path="dashboard" element={<Dashboard />} />

        <Route path="cases" element={<Cases />} />
        <Route path="evidence" element={<EvidenceList />} />
        <Route path="evidence/:hash" element={<EvidenceDetail />} />
        <Route path="audit-log" element={<AuditLog />} />
        <Route path="attestations" element={<AttestationsList />} />
        <Route path="attestations/:id" element={<AttestationDetail />} />
        <Route path="derived" element={<Derived />} />
        <Route path="portal"  element={<Portal />} />
        <Route path="proofs/:proof_id" element={<InferenceProofView />} />
      </Route>
    </Routes>
  )
}
