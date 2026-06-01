const path = require("path");

describe("policy", () => {
  let checkStartup, validateCwd;
  const EXIT_SPY = jest.spyOn(process, "exit").mockImplementation(() => { throw new Error("process.exit"); });

  beforeEach(() => {
    jest.resetModules();
    delete process.env.OCTOWIZ_ALLOWED_ROOTS;
  });

  afterEach(() => EXIT_SPY.mockClear());

  describe("checkStartup", () => {
    it("exits when OCTOWIZ_ALLOWED_ROOTS is not set", () => {
      ({ checkStartup } = require("../src/policy"));
      expect(() => checkStartup()).toThrow("process.exit");
      expect(EXIT_SPY).toHaveBeenCalledWith(1);
    });

    it("exits when OCTOWIZ_ALLOWED_ROOTS is empty string", () => {
      process.env.OCTOWIZ_ALLOWED_ROOTS = "";
      ({ checkStartup } = require("../src/policy"));
      expect(() => checkStartup()).toThrow("process.exit");
    });

    it("does not exit when OCTOWIZ_ALLOWED_ROOTS is set", () => {
      process.env.OCTOWIZ_ALLOWED_ROOTS = "/tmp/allowed";
      ({ checkStartup } = require("../src/policy"));
      expect(() => checkStartup()).not.toThrow();
    });
  });

  describe("validateCwd", () => {
    beforeEach(() => {
      process.env.OCTOWIZ_ALLOWED_ROOTS = "/allowed/root:/other/root";
      ({ validateCwd } = require("../src/policy"));
    });

    it("accepts a path under an allowed root", () => {
      const result = validateCwd("/allowed/root/project");
      expect(result).toBe(path.resolve("/allowed/root/project"));
    });

    it("accepts the allowed root itself", () => {
      expect(() => validateCwd("/allowed/root")).not.toThrow();
    });

    it("rejects a path outside allowed roots", () => {
      expect(() => validateCwd("/not/allowed/project")).toThrow(/not.*allowed/i);
    });

    it("rejects a path that is a prefix of a root but not under it", () => {
      expect(() => validateCwd("/allowed")).toThrow(/not.*allowed/i);
    });

    it("throws when cwd is missing", () => {
      expect(() => validateCwd("")).toThrow("cwd is required");
    });

    it("throws when cwd is not a string", () => {
      expect(() => validateCwd(null)).toThrow("cwd is required");
    });
  });
});
