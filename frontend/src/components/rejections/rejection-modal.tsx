"use client";
import { LinkedEntryModal } from "@/components/workflows/linked-entry-modal";
export function RejectionModal({open,onClose,onSaved}:{open:boolean;onClose:()=>void;onSaved:(message:string)=>void}) {
  return open?<LinkedEntryModal mode="unit-rejection" onClose={onClose} onSaved={onSaved}/>:null;
}
