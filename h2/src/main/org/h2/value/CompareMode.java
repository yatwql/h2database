/*
 * Copyright 2004-2025 H2 Group. Multiple-Licensed under the MPL 2.0,
 * and the EPL 1.0 (https://h2database.com/html/license.html).
 * Initial Developer: H2 Group
 */
package org.h2.value;

import java.nio.charset.Charset;
import java.text.Collator;
import java.util.Locale;
import java.util.Objects;

import org.h2.util.StringUtils;

/**
 * Instances of this class can compare strings. Case sensitive and case
 * insensitive comparison is supported, and comparison using a collator.
 */
public class CompareMode {

    /**
     * This constant means there is no collator set, and the default string
     * comparison is to be used.
     */
    public static final String OFF = "OFF";

    /**
     * This constant means the default collator should be used, even if ICU4J is
     * in the classpath.
     */
    public static final String DEFAULT = "DEFAULT_";

    /**
     * This constant means ICU4J should be used (this will fail if it is not in
     * the classpath).
     */
    public static final String ICU4J = "ICU4J_";

    /**
     * This constant means the charset specified should be used.
     * This will fail if the specified charset does not exist.
     */
    public static final String CHARSET = "CHARSET_";

    private static Locale[] LOCALES;

    private static volatile CompareMode lastUsed;

    private static final boolean CAN_USE_ICU4J;

    static {
        boolean b = false;
        try {
            Class.forName("com.ibm.icu.text.Collator");
            b = true;
        } catch (Exception e) {
            // ignore
        }
        CAN_USE_ICU4J = b;
    }

    private final String name;
    private final int strength;

    protected CompareMode(String name, int strength) {
        this.name = name;
        this.strength = strength;
    }

    /**
     * Create a new compare mode with the given collator and strength. If
     * required, a new CompareMode is created, or if possible the last one is
     * returned. A cache is used to speed up comparison when using a collator;
     * CollationKey objects are cached.
     *
     * @param name the collation name or null
     * @param strength the collation strength
     * @return the compare mode
     */
    public static CompareMode getInstance(String name, int strength) {
        CompareMode last = lastUsed;
        if (last != null && Objects.equals(last.name, name) && last.strength == strength) {
            return last;
        }
        if (name == null || name.equals(OFF)) {
            last = new CompareMode(name, strength);
        } else {
            boolean useICU4J;
            if (name.startsWith(ICU4J)) {
                useICU4J = true;
                name = name.substring(ICU4J.length());
            } else if (name.startsWith(DEFAULT)) {
                useICU4J = false;
                name = name.substring(DEFAULT.length());
            } else if (name.startsWith(CHARSET)) {
                useICU4J = false;
            } else {
                useICU4J = CAN_USE_ICU4J;
            }
            if (useICU4J) {
                last = new CompareModeIcu4J(name, strength);
            } else {
                last = new CompareModeDefault(name, strength);
            }
        }
        lastUsed = last;
        return last;
    }

    /**
     * Returns available locales for collations.
     *
     * @param onlyIfInitialized
     *            if {@code true}, returns {@code null} when locales are not yet
     *            initialized
     * @return available locales for collations.
     */
    public static Locale[] getCollationLocales(boolean onlyIfInitialized) {
        Locale[] locales = LOCALES;
        if (locales == null && !onlyIfInitialized) {
            LOCALES = locales = Collator.getAvailableLocales();
        }
        return locales;
    }

    /**
     * Compare two characters in a string.
     *
     * @param a the first string
     * @param ai the character index in the first string
     * @param b the second string
     * @param bi the character index in the second string
     * @param ignoreCase true if a case-insensitive comparison should be made
     * @return true if the characters are equals
     */
    public boolean equalsChars(String a, int ai, String b, int bi, boolean ignoreCase) {
        char ca = a.charAt(ai);
        char cb = b.charAt(bi);
        if (ca == cb) {
            return true;
        }
        if (ignoreCase) {
            if (Character.toUpperCase(ca) == Character.toUpperCase(cb)
                    || Character.toLowerCase(ca) == Character.toLowerCase(cb)) {
                return true;
            }
        }
        return false;
    }

    /**
     * Compare two strings.
     *
     * @param a the first string
     * @param b the second string
     * @param ignoreCase true if a case-insensitive comparison should be made
     * @return -1 if the first string is 'smaller', 1 if the second string is
     *         smaller, and 0 if they are equal
     */
    public int compareString(String a, String b, boolean ignoreCase) {
        if (ignoreCase) {
            return a.compareToIgnoreCase(b);
        }
        return a.compareTo(b);
    }

    /**
     * Get the collation name.
     *
     * @param l the locale
     * @return the name of the collation
     */
    public static String getName(Locale l) {
        Locale english = Locale.ENGLISH;
        String name = l.getDisplayLanguage(english) + ' ' +
                l.getDisplayCountry(english) + ' ' + l.getVariant();
        name = StringUtils.toUpperEnglish(name.trim().replace(' ', '_'));
        return name;
    }

    /**
     * Compare name of the locale with the given name. The case of the name
     * is ignored.
     *
     * @param locale the locale
     * @param name the name
     * @return true if they match
     */
    static boolean compareLocaleNames(Locale locale, String name) {
        return name.equalsIgnoreCase(locale.toString()) || name.equalsIgnoreCase(locale.toLanguageTag()) ||
                name.equalsIgnoreCase(getName(locale));
    }

    /**
     * Get the collator object for the given language name or language / country
     * combination.
     *
     * @param name the language name
     * @return the collator
     */
    public static Collator getCollator(String name) {
        Collator result = null;
        if (name.startsWith(ICU4J)) {
            name = name.substring(ICU4J.length());
        } else if (name.startsWith(DEFAULT)) {
            name = name.substring(DEFAULT.length());
        } else if (name.startsWith(CHARSET)) {
            return new CharsetCollator(Charset.forName(name.substring(CHARSET.length())));
        }
        int length = name.length();
        if (length == 2) {
            Locale locale = new Locale(StringUtils.toLowerEnglish(name), "");
            if (compareLocaleNames(locale, name)) {
                result = Collator.getInstance(locale);
            }
        } else if (length == 5) {
            // LL_CC (language_country)
            int idx = name.indexOf('_');
            if (idx >= 0) {
                String language = StringUtils.toLowerEnglish(name.substring(0, idx));
                String country = name.substring(idx + 1);
                Locale locale = new Locale(language, country);
                if (compareLocaleNames(locale, name)) {
                    result = Collator.getInstance(locale);
                }
            }
        } else if (name.indexOf('-') > 0) {
            Locale locale = Locale.forLanguageTag(name);
            if (!locale.getLanguage().isEmpty()) {
                return Collator.getInstance(locale);
            }
        }
        if (result == null) {
            for (Locale locale : getCollationLocales(false)) {
                if (compareLocaleNames(locale, name)) {
                    result = Collator.getInstance(locale);
                    break;
                }
            }
        }
        return result;
    }

    public String getName() {
        return name == null ? OFF : name;
    }

    public int getStrength() {
        return strength;
    }

    @Override
    public boolean equals(Object obj) {
        if (obj == this) {
            return true;
        } else if (!(obj instanceof CompareMode)) {
            return false;
        }
        CompareMode o = (CompareMode) obj;
        if (!getName().equals(o.getName())) {
            return false;
        }
        if (strength != o.strength) {
            return false;
        }
        return true;
    }

    @Override
    public int hashCode() {
        int result = 1;
        result = 31 * result + getName().hashCode();
        result = 31 * result + strength;
        return result;
    }

}
