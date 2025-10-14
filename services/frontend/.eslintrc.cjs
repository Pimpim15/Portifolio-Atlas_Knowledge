module.exports = {
  root: true,
  env: {
    browser: true,
    es2023: true,
  },
  extends: ["plugin:vue/vue3-essential", "eslint:recommended", "@vue/eslint-config-typescript"],
  parserOptions: {
    ecmaVersion: "latest",
    sourceType: "module",
  },
  rules: {},
};
