import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Layout } from "./components/Layout";
import { Dashboard } from "./pages/Dashboard";
import { Cases } from "./pages/Cases";
import { NewCase } from "./pages/NewCase";
import { CaseView } from "./pages/CaseView";
import { Sweeps } from "./pages/Sweeps";
import { Templates } from "./pages/Templates";
import { Benchmarks } from "./pages/Benchmarks";
import { Settings } from "./pages/Settings";

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/cases" element={<Cases />} />
            <Route path="/cases/new" element={<NewCase />} />
            <Route path="/cases/:id/*" element={<CaseView />} />
            <Route path="/sweeps" element={<Sweeps />} />
            <Route path="/templates" element={<Templates />} />
            <Route path="/benchmarks" element={<Benchmarks />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
