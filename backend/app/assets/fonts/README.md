# Embedded receipt fonts

Unmodified Noto Sans, Noto Sans Devanagari and Noto Sans Telugu Regular from
https://github.com/notofonts/noto-fonts/tree/main/hinted/ttf.
Redistributed under the bundled SIL Open Font License (`OFL.txt`).
No proprietary fonts or runtime network downloads are used.
Latin/Greek/Cyrillic, the rupee symbol, Devanagari and Telugu use these embedded
fonts with HarfBuzz shaping. Other missing glyphs are rendered explicitly as
`[U+XXXX]`, not silently replaced with question marks. This is not a claim of
universal script support. Record values remain unchanged in the JSON API.
