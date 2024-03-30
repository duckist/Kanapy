CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id BIGINT PRIMARY KEY,
    prefix TEXT NOT NULL,
    disabled_modules TEXT []
);

CREATE TABLE IF NOT EXISTS logging_activity (
    -- in cases of when the user/bot leaves and can't log anymore.
    activity_at TIMESTAMP WITH TIME ZONE NOT NULL,
    activity_type INT NOT NULL,
    -- this is either `0` (paused) or `1` (resumed)
    user_id BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS username_history (
    user_id BIGINT NOT NULL,
    time_changed TIMESTAMP WITH TIME ZONE NOT NULL,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS avatar_history (
    user_id BIGINT NOT NULL,
    changed_at TIMESTAMP WITH TIME ZONE NOT NULL,
    avatar_url TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS anime_reminders (
    user_id BIGINT NOT NULL,
    anilist_id INT NOT NULL,
    PRIMARY KEY (user_id, anilist_id)
);

CREATE OR REPLACE FUNCTION toggle_reminder(
    uid BIGINT, 
    aid INT
) RETURNS NUMERIC AS $$ DECLARE row_exists NUMERIC;

BEGIN
SELECT
    1 INTO row_exists
FROM
    anime_reminders
WHERE
    user_id = uid
    and anilist_id = aid;

IF (row_exists > 0) THEN
    DELETE FROM
        anime_reminders
    WHERE
        user_id = uid
        and anilist_id = aid;

    RETURN 0;
ELSE
    INSERT INTO
        anime_reminders (user_id, anilist_id)
    VALUES
        (uid, aid);

    RETURN 1;
END IF;

END;

$$ LANGUAGE plpgsql;