/** Sources and privacy page ("Források és adatvédelem"). */
export const sourcesHu = {
	title: 'Források és adatvédelem',

	prices_title: 'Bolti árak',
	prices_text:
		'A bolti árak a GVH Árfigyelő nyilvános adataiból származnak. Minden ár mellett feltüntetjük a forrást és az adatok dátumát.',
	// hu-HU dates end with a full stop, so no full stop follows {date} or {period}.
	prices_date: 'A jelenlegi adatok dátuma: {date}',
	prices_scope:
		'A „legolcsóbb” mindig a kiválasztott közeli boltokra és az adott napi GVH-adatokra vonatkozik. Ahol nincs bolti szintű ár, a lánc jellemző árát mutatjuk, és ezt jelöljük.',
	gvh_link: 'arfigyelo.gvh.hu',

	ksh_title: 'Becsült árak (KSH)',
	ksh_text:
		'A GVH Árfigyelőben nem szereplő alapanyagoknál a KSH havi országos átlagárát mutatjuk „becsült országos átlagár (KSH)” címkével. Ez nem bolti ár, és nem számítjuk bele a bolti végösszegbe.',
	ksh_license: 'A KSH STADAT ara0044 tábla adatai CC BY 4.0 licenc alatt használhatók.',
	ksh_period: 'A KSH-adatok időszaka: {period}',
	ksh_link: 'KSH STADAT ara0044',
	ksh_license_link: 'CC BY 4.0 licenc',

	nutrition_title: 'Tápérték',
	nutrition_text:
		'Tápértékadatok még nem érhetők el. Ha lesznek, nyílt összetételi táblákból számoljuk őket, forrásmegjelöléssel.',

	recipes_title: 'Receptek',
	recipes_text:
		'A receptek saját, eredeti szövegek. Amíg valaki ténylegesen meg nem főzte őket, „kipróbálatlan recept” jelölést kapnak.',

	privacy_title: 'Adatvédelem',
	device_title: 'Ami a készülékeden marad',
	device_plan:
		'a heti terv és a kosár, a bevásárlólista pipái és választásai, valamint a legutóbb betöltött lista és a kiválasztott bolt árai (hogy kapcsolat nélkül is használható legyen)',
	device_household: 'a háztartás mérete, az étkezések száma és a keresési sugár',
	device_pantry: 'a kamra és a kizárt alapanyagok, címkék',
	device_location: 'a helymeghatározás engedélye, a választott kerület vagy a hozzávetőleges helyzet',
	device_language: 'a választott nyelv',
	device_cache:
		'Az offline működéshez a böngésző eltárolja az alkalmazás fájljait és a nyilvános adatokat (boltlista, alapanyagok, receptek). Ezek nem személyes adatok.',

	server_title: 'Amit a szerverre küldünk',
	server_recipes: 'a kiválasztott receptek azonosítóit és az adagok számát',
	server_ingredients: 'az alapanyagok azonosítóit és mennyiségeit',
	server_stores: 'a kiválasztott boltok azonosítóit',
	server_plan:
		'heti terv kérésekor a napok, az étkezések és a fők számát, valamint a kizárt címkéket és alapanyagokat, amelyeket csak az adott számításhoz használunk',
	server_never:
		'A helyzetedet, a címedet vagy bármilyen személyes azonosítót soha nem küldjük el. A szerver nem tárol és nem naplóz semmit a kéréseid tartalmából.',

	cookies_title: 'Sütik és analitika',
	cookies_text: 'Nem használunk sütiket, analitikát vagy követőkódot, és nem töltünk be külső tartalmat.',
	delete_text: 'Az adataidat bármikor törölheted itt:',
	delete_link: 'Beállítások',

	contact_title: 'Kapcsolat',
	contact_text: 'Elérhetőség: hamarosan.',

	disclaimer_title: 'Jogi nyilatkozat'
} as const;
