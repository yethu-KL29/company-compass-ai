import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Documents } from "../features/documents/DocumentLibrary";
import { DocumentManager } from "../features/documents/DocumentManager";

const document = {
  id: "doc-overview",
  title: "Company overview",
  source_url: "https://company.example/about",
  revision: 2,
  version: "version-2",
  observed_at: "2026-10-31T10:00:00Z",
  source_kind: "admin_edit",
  chunk_count: 3,
  content: "Reviewed company content. <script>alert('unsafe')</script>",
};
const response = (body: unknown, status = 200) =>
  Promise.resolve({ ok: status < 400, status, json: async () => body });
afterEach(() => vi.unstubAllGlobals());

describe("company document management", () => {
  it("browses stable document metadata and safely displays full content and provenance", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        response(url === "/api/documents" ? [document] : document),
      ),
    );
    render(<Documents />);
    fireEvent.click(
      await screen.findByRole("button", { name: /Company overview/ }),
    );
    expect(await screen.findByText(document.content)).toBeInTheDocument();
    expect(screen.getAllByText("Admin-edited").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/doc-overview/).length).toBeGreaterThan(0);
    expect(globalThis.document.querySelector("script:not([type])")).toBeNull();
  });

  it("publishes full edits with admin authentication and the expected revision", async () => {
    const fetch = vi.fn((url: string, options?: RequestInit) =>
      response(
        options?.method === "PUT"
          ? {
              ...document,
              title: "Updated title",
              content: "Reviewed replacement",
              revision: 3,
            }
          : url === "/api/documents"
            ? [document]
            : document,
      ),
    );
    vi.stubGlobal("fetch", fetch);
    render(<DocumentManager token="test-admin" refreshKey={0} />);
    fireEvent.change(await screen.findByLabelText("Document to edit"), {
      target: { value: document.id },
    });
    await screen.findByDisplayValue(document.content);
    fireEvent.change(screen.getByLabelText("Document title"), {
      target: { value: "Updated title" },
    });
    fireEvent.change(screen.getByLabelText("Full document content"), {
      target: { value: "Reviewed replacement" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save and re-ingest" }));
    await screen.findByText(/Published document revision 3/);
    const call = fetch.mock.calls.find(
      ([, options]) => options?.method === "PUT",
    )!;
    expect(call[0]).toBe("/api/admin/documents/doc-overview");
    expect(call[1]?.headers).toEqual(
      expect.objectContaining({ "X-Admin-Token": "test-admin" }),
    );
    expect(JSON.parse(call[1]?.body as string)).toEqual({
      title: "Updated title",
      content: "Reviewed replacement",
      expected_revision: 2,
    });
  });

  it.each([409, 502])(
    "preserves unsaved content after a %s response",
    async (status) => {
      vi.stubGlobal(
        "fetch",
        vi.fn((url: string, options?: RequestInit) =>
          response(
            options?.method === "PUT"
              ? {
                  detail:
                    status === 409 ? "Document changed" : "Indexing failed",
                }
              : url === "/api/documents"
                ? [document]
                : document,
            options?.method === "PUT" ? status : 200,
          ),
        ),
      );
      render(<DocumentManager token="test-admin" refreshKey={0} />);
      fireEvent.change(await screen.findByLabelText("Document to edit"), {
        target: { value: document.id },
      });
      await screen.findByDisplayValue(document.content);
      fireEvent.change(screen.getByLabelText("Full document content"), {
        target: { value: "My unsaved correction" },
      });
      fireEvent.click(
        screen.getByRole("button", { name: "Save and re-ingest" }),
      );
      await waitFor(() =>
        expect(screen.getByRole("alert")).toBeInTheDocument(),
      );
      expect(screen.getByLabelText("Full document content")).toHaveValue(
        "My unsaved correction",
      );
      if (status === 409)
        expect(
          screen.getByRole("button", { name: /Reload published version/ }),
        ).toBeInTheDocument();
      else
        expect(screen.getByRole("alert")).toHaveTextContent(
          "previous published document remains available",
        );
    },
  );
});
