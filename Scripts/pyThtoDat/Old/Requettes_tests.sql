-- Liste des centerlines
SELECT
	CENTRELINE.ID As Num,
	SURVEY.NAME As SURVEY_NAME,
	SURVEY.FULL_NAME As Survey_Full_Name,
	SURVEY.TITLE As Survey_Title,
	CENTRELINE.TITLE,
	CENTRELINE.TOPO_DATE As SURVEY_DATE,
	Topo_Info.Noms_Prenoms_Topo,
	CENTRELINE.EXPLO_DATE,
	Explo_Info.Noms_Prenoms_Explo,
	CENTRELINE.LENGTH,
	CENTRELINE.SURFACE_LENGTH,
	CENTRELINE.DUPLICATE_LENGTH
FROM CENTRELINE
JOIN SURVEY On CENTRELINE.SURVEY_ID = SURVEY.ID
LEFT JOIN (
	SELECT
		TOPO.CENTRELINE_ID,
		GROUP_CONCAT(CONCAT(PERSON.NAME, ' ', PERSON.SURNAME), ', ') As Noms_Prenoms_Topo
	FROM TOPO  
	LEFT JOIN PERSON On TOPO.PERSON_ID = PERSON.ID
	-- WHERE TOPO.CENTRELINE_ID = 28
) AS Topo_Info ON CENTRELINE.ID = Topo_Info.CENTRELINE_ID
LEFT JOIN (
	SELECT
		EXPLO.CENTRELINE_ID,
		GROUP_CONCAT(CONCAT(PERSON.NAME, ' ', PERSON.SURNAME), ', ') As Noms_Prenoms_Explo
	FROM EXPLO  
	LEFT JOIN PERSON On EXPLO.PERSON_ID = PERSON.ID
	-- WHERE TOPO.CENTRELINE_ID = 28
) AS Explo_Info ON CENTRELINE.ID = Explo_Info.CENTRELINE_ID
LEFT JOIN PERSON On CENTRELINE.ID = PERSON.ID
ORDER BY SURVEY_DATE DESC