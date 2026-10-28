import React, {useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';

const API = import.meta.env.VITE_API_URL || 'https://nhs-carefinder-ai.onrender.com';
function App(){
  const [service,setService]=useState('GP surgery');
  const [postcode,setPostcode]=useState('');
  const [radius,setRadius]=useState(10);
  const [results,setResults]=useState([]);
  const [notice,setNotice]=useState('');
  const [busy,setBusy]=useState(false);
  const [question,setQuestion]=useState('');
  const [answer,setAnswer]=useState('');
  const [chatBusy,setChatBusy]=useState(false);
  async function search(e){
    e.preventDefault(); setBusy(true); setNotice(''); setResults([]);
    try{
      const r=await fetch(`${API}/api/search`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({service,postcode,radius_miles:Number(radius),limit:10})});
      const d=await r.json(); if(!r.ok) throw new Error(d.detail||'Search failed');
      setResults(d.results||[]); setNotice(d.notice||'');
    }catch(err){setNotice(`Unable to search at the moment: ${err.message}`)}finally{setBusy(false)}
  }
  async function ask(e){
    e.preventDefault();
    if(chatBusy || !question.trim()) return;
    setChatBusy(true);setAnswer('Thinking…');
    try{
      const r=await fetch(`${API}/api/chat`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:question.trim()})});
      const d=await r.json();
      if(r.status===429) throw new Error('Too many requests. Please wait about a minute before trying again.');
      if(!r.ok) throw new Error(d.detail||'The assistant could not answer that request.');
      setAnswer(d.answer||d.detail||'No response');
    }catch(err){
      setAnswer(err.message||'The assistant is temporarily unavailable. For urgent medical advice in England, contact NHS 111; for a life-threatening emergency, call 999.');
    }finally{setChatBusy(false)}
  }
  return <main>
    <header><div className="brand"><span className="cross">+</span><span>CareFinder <b>AI</b></span></div><span className="tag">NHS service navigation</span></header>
    <section className="hero"><div className="eyebrow">FIND THE RIGHT CARE</div><h1>Healthcare, closer<br/>to <em>you.</em></h1><p>Explore nearby NHS services and find contact information to help you take your next step.</p></section>
    <section className="search card"><h2>Find a healthcare service</h2><form onSubmit={search}>
      <label>What service do you need?<input value={service} onChange={e=>setService(e.target.value)} placeholder="e.g. GP, physiotherapy, hospital" required minLength="2"/></label>
      <div className="fields"><label>Postcode<input value={postcode} onChange={e=>setPostcode(e.target.value.toUpperCase())} placeholder="e.g. CO1 1AA" required minLength="5" maxLength="10"/></label><label>Search radius<select value={radius} onChange={e=>setRadius(e.target.value)}>{[5,10,15,25,50].map(x=><option key={x} value={x}>{x} miles</option>)}</select></label></div>
      <button disabled={busy}>{busy?'Searching…':'Find services →'}</button>
    </form></section>
    {notice&&<div className="notice" role="status">{notice}</div>}
    {!!results.length&&<section className="results"><h2>Services found <small>{results.length} results</small></h2>{results.map((p,i)=><article className="provider card" key={p.organisation_code||i}><div><div className="pill">{p.service}</div><h3>{p.name}</h3><p>{p.address}</p>{p.distance_miles!=null&&<small>{p.distance_miles} miles away</small>}</div><div className="contact">{p.phone&&<a href={`tel:${p.phone}`}>{p.phone}</a>}{p.website&&<a href={p.website} target="_blank" rel="noreferrer">Website ↗</a>}</div></article>)}</section>}
    <section className="assistant card"><div className="eyebrow">CARE NAVIGATION ASSISTANT</div><h2>Not sure where to start?</h2><p>Ask a general question about NHS services or care pathways.</p><form onSubmit={ask}><textarea value={question} onChange={e=>setQuestion(e.target.value)} placeholder="How do I find a specialist?" required maxLength="1200"/><button disabled={chatBusy}>{chatBusy?'Thinking…':'Ask assistant →'}</button></form>{answer&&<div className="answer" role="status">{answer}</div>}</section>
    <footer><strong>Important</strong><p>This tool does not diagnose conditions, recommend surgery, book appointments or confirm service availability. For life-threatening emergencies call <b>999</b>. For urgent medical advice contact <b>NHS 111</b>.</p><p>CareFinder AI is an independent prototype and is not an official NHS service.</p></footer>
  </main>
}
createRoot(document.getElementById('root')).render(<App/>);
