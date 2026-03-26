import { useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getDataset, listTestCases, deleteTestCase, importCsv, exportCsvUrl } from '../api/datasets'
import styles from './DatasetDetailPage.module.css'

export default function DatasetDetailPage() {
  const { id } = useParams<{ id: string }>()
  const datasetId = Number(id)
  const queryClient = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)

  const { data: dataset } = useQuery({ queryKey: ['dataset', datasetId], queryFn: () => getDataset(datasetId) })
  const { data: testCases, isLoading } = useQuery({ queryKey: ['testcases', datasetId], queryFn: () => listTestCases(datasetId) })
  const deleteMut = useMutation({
    mutationFn: deleteTestCase,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['testcases', datasetId] }),
  })
  const importMut = useMutation({
    mutationFn: (file: File) => importCsv(datasetId, file),
    onSuccess: (data) => {
      alert(`Imported ${data.imported_count} test cases`)
      queryClient.invalidateQueries({ queryKey: ['testcases', datasetId] })
    },
  })

  function handleImport() {
    const file = fileRef.current?.files?.[0]
    if (file) importMut.mutate(file)
  }

  if (isLoading) return <div>Loading...</div>

  return (
    <div>
      <Link to="/datasets" className={styles.backLink}>← Back to Datasets</Link>
      <h1>{dataset?.name || 'Dataset'}</h1>
      <p className={styles.desc}>{dataset?.description}</p>
      <p className={styles.meta}>Type: {dataset?.target_type} | Tags: {dataset?.tags.join(', ') || 'none'}</p>

      <div className={styles.actions}>
        <input type="file" ref={fileRef} accept=".csv" style={{ display: 'none' }} onChange={handleImport} />
        <button className={styles.btn} onClick={() => fileRef.current?.click()}>Import CSV</button>
        <a href={exportCsvUrl(datasetId)} download className={styles.btn}>Export CSV</a>
      </div>

      <h2>Test Cases ({testCases?.length || 0})</h2>
      <table className={styles.table}>
        <thead>
          <tr><th>ID</th><th>Name</th><th>Data</th><th>Expected Result</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {testCases?.map(tc => (
            <tr key={tc.id}>
              <td>{tc.id}</td>
              <td>{tc.name}</td>
              <td className={styles.jsonCell}>{JSON.stringify(tc.data).slice(0, 80)}</td>
              <td className={styles.jsonCell}>{JSON.stringify(tc.expected_result).slice(0, 80)}</td>
              <td>
                <button className={styles.btnDanger} onClick={() => { if (confirm('Delete?')) deleteMut.mutate(tc.id) }}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {testCases?.length === 0 && <p className={styles.empty}>No test cases. Import a CSV or create via CLI/API.</p>}
    </div>
  )
}
