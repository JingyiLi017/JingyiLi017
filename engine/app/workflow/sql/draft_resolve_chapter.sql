-- :ctx = json string
WITH inp AS (
  SELECT
    CAST(:ctx AS jsonb) AS j,
    NULLIF((CAST(:ctx AS jsonb)->>'chapter_id'), '')::uuid AS chapter_id,
    NULLIF((CAST(:ctx AS jsonb)->>'book_id'), '')::uuid AS book_id,
    COALESCE(NULLIF((CAST(:ctx AS jsonb)->>'chapter_no'), '')::int, 1) AS chapter_no
),
ins AS (
  INSERT INTO chapter(book_id, "order", title)
  SELECT inp.book_id, inp.chapter_no, ''
  FROM inp
  WHERE inp.book_id IS NOT NULL
    AND inp.chapter_id IS NULL
    AND NOT EXISTS (
      SELECT 1 FROM chapter c0 WHERE c0.book_id = inp.book_id AND c0."order" = inp.chapter_no
    )
  RETURNING chapter_id
),
sel AS (
  SELECT c.chapter_id, c.book_id, c."order" AS chapter_no, c.title AS chapter_title
  FROM chapter c, inp
  WHERE (
    inp.chapter_id IS NOT NULL AND c.chapter_id = inp.chapter_id
  ) OR (
    inp.chapter_id IS NULL AND inp.book_id IS NOT NULL AND c.book_id = inp.book_id AND c."order" = inp.chapter_no
  )
  ORDER BY c."order"
  LIMIT 1
),
max_book AS (
  SELECT COALESCE(MAX(c2."order"), 1) AS max_order
  FROM chapter c2
  JOIN sel ON c2.book_id = sel.book_id
),
vol AS (
  SELECT v.volume_id, v.start_chapter_no, v.end_chapter_no
  FROM volume v
  JOIN sel ON v.book_id = sel.book_id
  WHERE sel.chapter_no BETWEEN v.start_chapter_no AND v.end_chapter_no
  ORDER BY v.volume_no
  LIMIT 1
)
SELECT jsonb_build_object(
  'chapter_id', (SELECT sel.chapter_id::text FROM sel),
  'book_id', (SELECT sel.book_id::text FROM sel),
  'chapter_no', COALESCE((SELECT sel.chapter_no FROM sel), (SELECT chapter_no FROM inp)),
  'chapter_title', COALESCE((SELECT sel.chapter_title FROM sel), ''),
  'planned_book_chapters', COALESCE((SELECT max_order FROM max_book), 1),
  'volume_id', (SELECT vol.volume_id::text FROM vol),
  'volume_start_chapter_no', COALESCE((SELECT vol.start_chapter_no FROM vol), (SELECT chapter_no FROM inp)),
  'volume_end_chapter_no', COALESCE((SELECT vol.end_chapter_no FROM vol), (SELECT chapter_no FROM inp)),
  'chapters_to_end', COALESCE((SELECT vol.end_chapter_no FROM vol), (SELECT chapter_no FROM inp)) - COALESCE((SELECT sel.chapter_no FROM sel), (SELECT chapter_no FROM inp)),
  'p_book', COALESCE(
    ROUND((COALESCE((SELECT sel.chapter_no FROM sel), (SELECT chapter_no FROM inp))::numeric) / GREATEST(1, (SELECT max_order FROM max_book))::numeric, 6),
    0
  ),
  'p_vol', COALESCE(
    ROUND(
      CASE
        WHEN (SELECT vol.end_chapter_no - vol.start_chapter_no FROM vol) > 0
        THEN ((COALESCE((SELECT sel.chapter_no FROM sel), (SELECT chapter_no FROM inp)) - (SELECT vol.start_chapter_no FROM vol))::numeric)
             / ((SELECT vol.end_chapter_no - vol.start_chapter_no FROM vol)::numeric)
        ELSE 0
      END, 6
    ),
    0
  )
) AS data;
