import { createContext, use, useEffect, useMemo, useState, type ReactNode } from "react";

export type Language = "ja" | "en";

interface LanguageContextValue {
  language: Language;
  setLanguage: (language: Language) => void;
  text: (japanese: string, english: string) => string;
}

const STORAGE_KEY = "soj-language";
const LanguageContext = createContext<LanguageContextValue>({
  language: "ja",
  // 単体表示するcomponentは日本語で動作し、provider外の操作には副作用を持たせない。
  setLanguage: () => undefined,
  text: (japanese) => japanese,
});

// 保存値が不正またはstorageを利用できない環境でも、日本語で表示を開始する。
function savedLanguage(): Language {
  try {
    return localStorage.getItem(STORAGE_KEY) === "en" ? "en" : "ja";
  } catch {
    return "ja";
  }
}

// 表示言語だけを共有・保存し、切り替え時も子componentの入力や通信stateを維持する。
export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>(savedLanguage);

  useEffect(() => {
    document.documentElement.lang = language;
    try {
      localStorage.setItem(STORAGE_KEY, language);
    } catch {
      // 保存を拒否するブラウザでも、この画面での言語切り替えは利用できる。
    }
  }, [language]);

  const value = useMemo<LanguageContextValue>(
    () => ({
      language,
      setLanguage,
      text: (japanese, english) => (language === "ja" ? japanese : english),
    }),
    [language],
  );

  return <LanguageContext value={value}>{children}</LanguageContext>;
}

// UI文言の選択を共有し、APIからのコマンド・実行出力には変換を加えない。
export function useLanguage(): LanguageContextValue {
  return use(LanguageContext);
}
