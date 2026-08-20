(()=>{
  const groups={
    anniversary:{label:'주년과 반주년',cls:'',items:[['1주년',2022,2],['1.5주년',2022,8],['2주년',2023,2],['2.5주년',2023,8],['3주년',2024,2],['3.5주년',2024,8],['4주년',2025,2],['4.5주년',2025,8],['5주년',2026,2],['5.5주년',2026,8],['6주년',2027,2]]},
    anime:{label:'애니와 미디어',cls:'event-anime',items:[['TVA 제작 발표',2023,1],['TVA 티저',2024,1],['TVA 방영',2024,4]]},
    fes:{label:'블루아카 페스',cls:'event-fes',items:[['3주년 페스',2024,1],['4주년 페스',2025,1],['5주년 페스',2026,1]]},
    live:{label:'공개 생방송',cls:'event-live',items:[['가을 SP',2022,10],['교토 SP',2024,4],['3.5 공개',2024,7],['Summer SP',2025,6],['4.5 공개',2025,7]]},
    story:{label:'메인 스토리',cls:'event-story',items:[['Vol.2 2장',2022,11],['최종편 개막',2023,1],['최종편 3장',2023,2],['최종편 4장',2023,3],['Vol.4 2장',2023,6],['Vol.1 3장 P3',2024,6]]},
    game:{label:'대형 게임 이벤트',cls:'event-game',items:[['F.SCT 공략전',2023,1],['A-H.A 점령전',2023,2],['Sheside outside',2024,7]]}
  };
  const monthly={},monthlyItems={},quarterly={};
  Object.entries(groups).forEach(([key,g])=>{monthly[key]={label:g.label,cls:g.cls,items:g.items,monthly:g.items};monthlyItems[key]=g.items;quarterly[key]={label:g.label,cls:g.cls,items:g.items.map(([name,year,month])=>[name,year,Math.ceil(month/3)])}});
  window.ATLAS_EVENTS={monthly,monthlyItems,quarterly};
})();
