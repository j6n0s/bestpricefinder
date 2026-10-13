/** Settings page ("Beállítások"). */
export const settingsHu = {
	title: 'Beállítások',
	intro: 'Ezeket a beállításokat csak ezen a készüléken tároljuk.',
	storage_unavailable:
		'A böngésző nem engedi az adatok mentését (például privát módban). A beállítások csak addig maradnak meg, amíg ezt a lapot be nem zárod.',

	household_title: 'Háztartás',
	people_label: 'Hány főre tervezel?',
	people_decrease: 'Eggyel kevesebb fő',
	people_increase: 'Eggyel több fő',
	people_value_one: '{count} fő',
	people_value_other: '{count} fő',
	slots_label: 'Étkezések naponta',
	slots_3: '3 étkezés: reggeli, ebéd, vacsora',
	slots_5: '5 étkezés: reggeli, tízórai, ebéd, uzsonna, vacsora',

	stores_title: 'Boltok keresése',
	radius_label: 'Keresési sugár',
	radius_hint: 'Ennyi távolságon belül keressük a boltokat ({min}–{max} km).',

	language_title: 'Nyelv',
	language_hu: 'Magyar',
	language_en: 'English',

	location_title: 'Helyzet és kerület',
	location_status_label: 'Helymeghatározás',
	location_status_unset: 'Nincs engedélyezve.',
	// {time} is a date-time ("2026. 10. 13. 4:31"); {date} is a date that already ends with a full stop.
	location_status_granted: 'Engedélyezve. A hozzávetőleges helyzet ideje: {time}.',
	location_status_declined: 'Elutasítva. Kerületet bármikor választhatsz.',
	location_revoke: 'Engedély visszavonása',
	location_revoked:
		'A tárolt helyzetet töröltük. A böngésző engedélyét a böngésző beállításaiban is visszavonhatod.',
	location_source_label: 'A távolságokat innen számoljuk:',
	location_source_none: 'még nincs megadva.',
	location_source_device: 'a készülék hozzávetőleges helyzete.',
	location_use_district: 'Kerület használata',

	pantry_title: 'Kamra',
	exclusions_title: 'Kizárt alapanyagok és címkék',

	clear_title: 'Adatok törlése',
	clear_description:
		'Törli az összes ezen a készüléken tárolt adatot: a tervet, a beállításokat, a kamrát, a kizárásokat, a helyzetet és a lista pipáit.',
	clear_button: 'Minden adat törlése',
	clear_confirm_title: 'Biztosan törlöd az összes adatot?',
	clear_confirm_text: 'A törlés nem vonható vissza.',
	clear_confirm_yes: 'Igen, mindent törlök',
	clear_confirm_no: 'Mégse',
	clear_done: 'Minden adat törölve.',
	clear_partial:
		'Ebből a munkamenetből minden adatot töröltünk, de a böngésző nem engedte elérni a tárolóját. Ha korábban mentett adatot, azt a böngésző beállításaiban (webhelyadatok) törölheted.'
} as const;
