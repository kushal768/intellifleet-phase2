import { useState } from "react";
import { uploadCSVs, sendChat } from "./api";

export default function Sidebar({ setLegs }) {
  const [air, setAir] = useState(null);
  const [road, setRoad] = useState(null);
  const [query, setQuery] = useState("");

  return (
    <div className="sidebar">
      <h3>Upload CSVs</h3>
      <input type="file" onChange={e=>setAir(e.target.files[0])}/>
      <input type="file" onChange={e=>setRoad(e.target.files[0])}/>
      <button onClick={()=>uploadCSVs(air, road)}>Upload</button>

      <h3>Chat</h3>
      <input value={query} onChange={e=>setQuery(e.target.value)} />
      <button onClick={async()=>{
        const res = await sendChat(query);
        setLegs(res.legs);
      }}>Ask</button>
    </div>
  );
}
