/** SDK-shaped local test double only; no Google script, tiles, key or paid request. */
import type { Page } from "@playwright/test";
declare global { interface Window { __mapsFixture: {maps:number;activeOverlays:number;overlays:number;pans:number;zooms:number;pointKinds:string[]} } }
export async function installMapsFixture(page: Page) {
  await page.addInitScript(()=>{
    const stats={maps:0,activeOverlays:0,overlays:0,pans:0,zooms:0,pointKinds:[] as string[]};
    window.__mapsFixture=stats;
    class MapStub {
      constructor(root:HTMLElement) {stats.maps++;root.innerHTML='<div data-testid="synthetic-google-map" style="height:100%;display:grid;place-items:center;background:linear-gradient(30deg,#e3edef,#f4f0f7)">Synthetic SDK test double · no live Google imagery</div>';}
      addListener(name:string,fn:()=>void) {if(name==='tilesloaded')setTimeout(fn,0);return{remove(){}};}
      panTo(){stats.pans++;}setZoom(){stats.zooms++;}
    }
    class Feature {constructor(public value:{properties?:Record<string,unknown>}){}getProperty(name:string){return this.value.properties?.[name];}}
    class DataStub {
      static Point=class {constructor(public position:unknown){}};
      features:Feature[]=[];
      constructor(_options:unknown){void _options;}
      add(value:{properties?:Record<string,unknown>}){const f=new Feature(value);this.features.push(f);stats.pointKinds=this.features.map(x=>String(x.getProperty('kind')));return f;}
      remove(f:Feature){this.features=this.features.filter(x=>x!==f);}
      forEach(fn:(f:Feature)=>void){[...this.features].forEach(fn);}
      setStyle(){}setMap(){}addListener(){return{remove(){}};}
    }
    class Overlay {
      current=false;
      constructor(url:string){if(!url.startsWith('data:image/png'))throw new Error('Expected generated scenario pixels only');stats.overlays++;}
      setMap(map:unknown){if(this.current)stats.activeOverlays--;this.current=!!map;if(this.current)stats.activeOverlays++;}
    }
    class Info {setContent(){}setPosition(){}open(){}close(){}}
    Object.defineProperty(window,'google',{configurable:true,value:{maps:{Map:MapStub,Data:DataStub,GroundOverlay:Overlay,InfoWindow:Info,SymbolPath:{CIRCLE:0},event:{clearInstanceListeners(){}}}}});
  });
}
