import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { MotionProvider } from "./motion";
import { createQueryClient } from "./api/client";
import "@fontsource-variable/plus-jakarta-sans/wght.css";
import "@fontsource-variable/jetbrains-mono/wght.css";
import "./styles.css";
import "./workspace.css";
import "./motion/motion.css";

const queryClient = createQueryClient();
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <MotionProvider>
          <App />
        </MotionProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
