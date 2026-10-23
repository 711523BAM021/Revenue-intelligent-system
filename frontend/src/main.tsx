import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import "./index.css";
import { ConversationDetail } from "./pages/ConversationDetail";
import { Conversations } from "./pages/Conversations";
import { Exports } from "./pages/Exports";
import { Imports } from "./pages/Imports";
import { ManagerBrief } from "./pages/ManagerBrief";
import { Overview } from "./pages/Overview";
import { Quality } from "./pages/Quality";
import { RoutingReview } from "./pages/RoutingReview";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Overview />} />
          <Route path="conversations" element={<Conversations />} />
          <Route path="conversations/:sourceType/:sourceId" element={<ConversationDetail />} />
          <Route path="routing" element={<RoutingReview />} />
          <Route path="brief" element={<ManagerBrief />} />
          <Route path="exports" element={<Exports />} />
          <Route path="imports" element={<Imports />} />
          <Route path="quality" element={<Quality />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
