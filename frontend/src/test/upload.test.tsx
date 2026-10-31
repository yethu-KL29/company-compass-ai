import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { DocumentUpload } from "../features/documents/DocumentUpload";

afterEach(() => vi.unstubAllGlobals());
it("uploads a document with multipart content, a title and admin authentication", async () => {
  const fetch = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({
      id: "uploaded-policy",
      title: "Reviewed policy",
      revision: 1,
      content: "Policy content",
      source_kind: "admin_upload",
    }),
  });
  vi.stubGlobal("fetch", fetch);
  render(<DocumentUpload token="test-admin" onUploaded={() => {}} />);
  expect(screen.getByLabelText("Upload title")).toHaveAttribute(
    "maxlength",
    "250",
  );
  const user = userEvent.setup();
  await user.upload(
    screen.getByLabelText("Document file"),
    new File(["Policy content"], "policy.md", { type: "text/markdown" }),
  );
  fireEvent.change(screen.getByLabelText("Upload title"), {
    target: { value: "Reviewed policy" },
  });
  const submit = screen.getByRole("button", { name: "Upload and ingest" });
  expect(submit).not.toBeDisabled();
  fireEvent.submit(submit.closest("form")!);
  await screen.findByText(/Uploaded Reviewed policy/);
  const options = fetch.mock.calls[0][1];
  expect(options.method).toBe("POST");
  expect(options.headers["X-Admin-Token"]).toBe("test-admin");
  expect(options.headers["Content-Type"]).toBeUndefined();
  expect(options.body).toBeInstanceOf(FormData);
  expect(options.body.get("title")).toBe("Reviewed policy");
  expect(options.body.has("source_url")).toBe(false);
  expect(options.body.get("file").name).toBe("policy.md");
});

it("rejects files beyond the backend's exact ten-million-byte limit", async () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  render(<DocumentUpload token="test-admin" onUploaded={() => {}} />);
  const user = userEvent.setup();
  await user.upload(
    screen.getByLabelText("Document file"),
    new File([new Uint8Array(10_000_001)], "oversized.txt", {
      type: "text/plain",
    }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent("10 MB");
  expect(fetch).not.toHaveBeenCalled();
});
