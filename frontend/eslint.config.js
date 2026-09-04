import globals from "globals";
import pluginJs from "@eslint/js";
import pluginReact from "@eslint-react/eslint-plugin";
import pluginReactHooks from "eslint-plugin-react-hooks";
import prettier from "eslint-config-prettier";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: ["coverage/", "dist/"],
  },
  {
    files: ["**/*.cjs"],
    languageOptions: {
      globals: globals.commonjs,
    },
  },
  pluginJs.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["src/**/*.{js,jsx,ts,tsx}"],
    extends: [pluginReact.configs["recommended-typescript"]],
  },
  {
    files: ["**/*.{js,jsx,ts,tsx}"],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
      },
    },
    plugins: {
      "react-hooks": pluginReactHooks,
    },
    rules: {
      ...pluginReactHooks.configs.flat.recommended.rules,
      // 既存の非同期取得effectと用途別ref名は、現在のUI state modelでは意図した構造とする。
      "@eslint-react/naming-convention-ref-name": "off",
      "@eslint-react/set-state-in-effect": "off",
      "react-hooks/set-state-in-effect": "off",
    },
  },
  prettier,
);
