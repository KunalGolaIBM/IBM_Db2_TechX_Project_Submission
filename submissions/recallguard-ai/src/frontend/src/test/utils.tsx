import type { ReactElement } from "react";
import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DemoProvider } from "@/hooks/useDemo";

export function renderWithProviders(ui: ReactElement, { route = "/", path = "*" }: { route?: string; path?: string } = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <DemoProvider>
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route path={path} element={ui} />
            <Route path="/investigations/:id" element={<p>investigation page</p>} />
            <Route path="/incidents/:id" element={<p>incident page</p>} />
          </Routes>
        </MemoryRouter>
      </DemoProvider>
    </QueryClientProvider>,
  );
}
