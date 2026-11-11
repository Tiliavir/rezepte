declare module "lunr-languages/lunr.stemmer.support" {
  const register: (instance: typeof import("lunr")) => void;
  export default register;
}

declare module "lunr-languages/lunr.de" {
  const register: (instance: typeof import("lunr")) => void;
  export default register;
}

declare namespace lunr {
  const de: {
    trimmer: (token: Token) => Token | undefined;
    stemmer: (token: Token) => Token | undefined;
  };
}
