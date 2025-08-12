import globals from "globals";
import pluginJs from "@eslint/js";
import pluginReact from "eslint-plugin-react";
import pluginPrettier from "eslint-plugin-prettier";

export default [
    {
        languageOptions: {
          globals: {
            ...globals.browser,
            ...globals.node,
            ...globals.jest,
          },
          parserOptions: {
            ecmaVersion: "latest",
            sourceType: "module",
            ecmaFeatures: {
              jsx: true,
            },
          },
        },
    },
    pluginJs.configs.recommended,
	{
		files: ["**/*.js", "**/*.cjs", "**/*.mjs", "**/*.jsx"],
        plugins: {
          react: pluginReact,
          prettier: pluginPrettier,
        },
        settings: {
          react: {
            version: "detect",
          },
        },  
		rules: {
			"prefer-const": "warn",
			"no-constant-binary-expression": "error",
            "react/react-in-jsx-scope": "off",
			...pluginReact.configs.recommended.rules,
			"react/jsx-uses-react": "error",
			"react/jsx-uses-vars": "error",
			"prettier/prettier": "error",
		},
	},
];